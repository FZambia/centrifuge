# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import six
import uuid
import time
from functools import partial

import tornado.web
import tornado.ioloop
from tornado.gen import coroutine, Return

from centrifuge import utils
from centrifuge.structure import Structure
from centrifuge.state.base import State
from centrifuge.log import logger
from centrifuge.forms import NamespaceForm, ProjectForm
from centrifuge.pubsub.base import BasePubSub


class Application(tornado.web.Application):

    # magic fake project ID for owner API purposes.
    MAGIC_PROJECT_ID = '_'

    # magic project param name to allow owner make API operations within project
    MAGIC_PROJECT_PARAM = '_project'

    # in milliseconds, how often this application will send ping message
    PING_INTERVAL = 5000

    # in seconds
    PING_MAX_DELAY = 10

    # in milliseconds, how often application will remove stale ping information
    PING_REVIEW_INTERVAL = 10000

    UNAUTHORIZED = 'unauthorized'

    PERMISSION_DENIED = 'permission denied'

    INTERNAL_SERVER_ERROR = 'internal server error'

    METHOD_NOT_FOUND = 'method not found'

    PROJECT_NOT_FOUND = 'project not found'

    NAMESPACE_NOT_FOUND = 'namespace not found'

    DUPLICATE_NAME = 'duplicate name'

    def __init__(self, *args, **kwargs):

        # create unique uid for this application
        self.uid = uuid.uuid4().hex

        # PUB/SUB manager class
        self.pubsub = BasePubSub(self)

        # initialize dict to keep administrator's connections
        self.admin_connections = {}

        # dictionary to keep client's connections
        self.connections = {}

        # dictionary to keep ping from nodes
        self.nodes = {}

        # application structure manager (projects, namespaces etc)
        self.structure = None

        # application state manager
        self.state = None

        # initialize dict to keep back-off information for projects
        self.back_off = {}

        # list of coroutines that must be done before message publishing
        self.pre_publish_callbacks = []

        # list of coroutines that must be done after message publishing
        self.post_publish_callbacks = []

        # initialize tornado's application
        super(Application, self).__init__(*args, **kwargs)

    def initialize(self):
        self.init_callbacks()
        self.init_structure()
        self.init_pubsub()
        self.init_state()
        self.init_ping()

    def init_structure(self):
        """
        Initialize structure manager using settings provided
        in configuration file.
        """
        custom_settings = self.settings['config']
        structure_settings = custom_settings.get('structure', {})

        # detect and apply database storage module
        storage_module = structure_settings.get(
            'storage', 'centrifuge.structure.sqlite'
        )
        storage = utils.import_module(storage_module)

        structure = Structure(self)
        structure.set_storage(storage)
        self.structure = structure

        def run_periodic_structure_update():
            # update structure periodically from database. This is necessary to be sure
            # that application has actual and correct structure information. Structure
            # updates also triggered in real-time by message passing through control channel,
            # but in rare cases those update messages can be lost because of some kind of
            # network errors
            structure.update()
            periodic_structure_update = tornado.ioloop.PeriodicCallback(
                structure.update, structure_settings.get('update_interval', 30)*1000
            )
            periodic_structure_update.start()

        tornado.ioloop.IOLoop.instance().add_callback(
            partial(
                storage.init_storage,
                structure,
                structure_settings.get('settings', {}),
                run_periodic_structure_update
            )
        )

        logger.info("Storage module: {0}".format(storage_module))

    def init_state(self):
        """
        Initialize state manager (for presence/history data).
        """
        config = self.settings['config']
        state_config = config.get("state", {})
        if not state_config:
            # use fake state
            logger.info("No State configured")
            self.state = State(self, fake=True)
        else:
            state_storage = state_config.get('storage', 'centrifuge.state.base.State')
            state_storage_class = utils.namedAny(state_storage)
            self.state = state_storage_class(self)
            tornado.ioloop.IOLoop.instance().add_callback(self.state.initialize)

    def init_pubsub(self):
        """
        Initialize and configure pub/sub manager.
        """
        self.pubsub.initialize()

    def init_callbacks(self):
        """
        Fill custom callbacks with callable objects provided in config.
        """
        config = self.settings['config']

        pre_publish_callbacks = config.get('pre_publish_callbacks', [])
        for callable_path in pre_publish_callbacks:
            callback = utils.namedAny(callable_path)
            self.pre_publish_callbacks.append(callback)

        post_publish_callbacks = config.get('post_publish_callbacks', [])
        for callable_path in post_publish_callbacks:
            callback = utils.namedAny(callable_path)
            self.post_publish_callbacks.append(callback)

    def send_ping(self, ping_message):
        self.pubsub.publish_control_message(ping_message)

    def review_ping(self):
        """
        Remove outdated information about other nodes.
        """
        now = time.time()
        outdated = []
        for node, updated_at in self.nodes.items():
            if now - updated_at > self.PING_MAX_DELAY:
                outdated.append(node)
        for node in outdated:
            try:
                del self.nodes[node]
            except KeyError:
                pass

    def init_ping(self):
        """
        Start periodic tasks for sending ping and reviewing ping.
        """
        message = {
            'app_id': self.uid,
            'method': 'ping',
            'params': {'uid': self.uid}
        }
        send_ping = partial(self.pubsub.publish_control_message, message)
        ping = tornado.ioloop.PeriodicCallback(send_ping, self.PING_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, ping.start
        )

        review_ping = tornado.ioloop.PeriodicCallback(self.review_ping, self.PING_REVIEW_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, review_ping.start
        )

    def send_control_message(self, message):
        """
        Send message to CONTROL channel. We use this channel to
        share commands between running instances.
        """
        self.pubsub.publish_control_message(message)

    def add_connection(self, project_id, user, uid, client):
        """
        Register new client's connection.
        """
        if project_id not in self.connections:
            self.connections[project_id] = {}
        if user and user not in self.connections[project_id]:
            self.connections[project_id][user] = {}
        if user:
            self.connections[project_id][user][uid] = client

    def remove_connection(self, project_id, user, uid):
        """
        Remove client's connection
        """
        try:
            del self.connections[project_id][user][uid]
        except KeyError:
            pass

        if project_id in self.connections and user in self.connections[project_id]:
            # clean connections
            if self.connections[project_id][user]:
                return
            try:
                del self.connections[project_id][user]
            except KeyError:
                pass
            if self.connections[project_id]:
                return
            try:
                del self.connections[project_id]
            except KeyError:
                pass

    def add_admin_connection(self, uid, client):
        """
        Register administrator's connection (from web-interface).
        """
        self.admin_connections[uid] = client

    def remove_admin_connection(self, uid):
        """
        Remove administrator's connection.
        """
        try:
            del self.admin_connections[uid]
        except KeyError:
            pass

    @coroutine
    def handle_ping(self, params):
        """
        Ping message received.
        """
        self.nodes[params.get('uid')] = time.time()

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe message received - unsubscribe client from certain channels.
        """
        project = params.get("project")
        user = params.get("user")
        namespace_name = params.get("namespace", None)
        channel = params.get("channel", None)

        if not user:
            # we don't need to block anonymous users
            raise Return((True, None))

        project_id = project['_id']

        # try to find user's connection
        user_connections = self.connections.get(project_id, {}).get(user, None)
        if not user_connections:
            raise Return((True, None))

        namespace, error = yield self.structure.get_namespace_by_name(
            project, namespace_name
        )
        if error:
            raise Return((None, error))
        if channel and not namespace:
            # namespace does not exist
            raise Return((True, None))

        namespace_name = namespace['name']

        for uid, connection in six.iteritems(user_connections):

            if not namespace_name and not channel:
                # unsubscribe from all channels
                for ns, channels in six.iteritems(connection.channels):
                    for chan in channels:
                        yield connection.handle_unsubscribe({
                            "namespace": ns,
                            "channel": chan
                        })

            elif namespace_name and not channel:
                # unsubscribe from all channels in namespace
                for cat, channels in six.iteritems(connection.channels):
                    if namespace_name != cat:
                        continue
                    for chan in channels:
                        yield connection.handle_unsubscribe({
                            "namespace": namespace_name,
                            "channel": chan
                        })
                raise Return((True, None))

            else:
                # unsubscribe from certain channel
                yield connection.handle_unsubscribe({
                    "namespace": namespace_name,
                    "channel": channel
                })

        raise Return((True, None))

    @coroutine
    def handle_update_structure(self, params):
        """
        Update structure message received - structure changed and other
        node sent us a signal about update.
        """
        result, error = yield self.structure.update()
        raise Return((result, error))

    # noinspection PyCallingNonCallable
    @coroutine
    def process_call(self, project, method, params):
        """
        Call appropriate method from this class according to specified method.
        Note, that all permission checking must be done before calling this method.
        """
        handle_func = getattr(self, "process_%s" % method, None)

        if handle_func:
            result, error = yield handle_func(project, params)
            raise Return((result, error))
        else:
            raise Return((None, self.METHOD_NOT_FOUND))

    @coroutine
    def publish_message(self, message, allowed_namespaces):
        """
        Publish event into PUB socket stream
        """
        project_id = message['project_id']
        namespace_name = message['namespace']
        channel = message['channel']

        if allowed_namespaces[namespace_name]['is_watching']:
            # send to admin channel
            self.pubsub.publish_admin_message(message)

        # send to event channel
        subscription_key = self.pubsub.get_subscription_key(
            project_id, namespace_name, channel
        )

        self.pubsub.publish(subscription_key, message)

        yield self.state.add_history_message(
            project_id, namespace_name, channel, message,
            history_size=allowed_namespaces[namespace_name]['history_size']
        )

        raise Return((True, None))

    @coroutine
    def prepare_message(self, project, allowed_namespaces, params, client):
        """
        Prepare message before actual publishing.
        """
        namespace_name = params.get('namespace')
        namespace, error = yield self.structure.get_namespace_by_name(
            project, namespace_name
        )
        if error:
            raise Return((None, error))
        if not namespace:
            raise Return((None, self.NAMESPACE_NOT_FOUND))
        namespace_name = namespace['name']

        namespace = allowed_namespaces.get(namespace_name, None)
        if not namespace:
            raise Return((None, "namespace not found in allowed namespaces"))

        data = params.get('data', None)

        message = {
            'project_id': project['_id'],
            'namespace': namespace['name'],
            'uid': uuid.uuid4().hex,
            'timestamp': int(time.time()),
            'client': client,
            'channel': params.get('channel'),
            'data': data
        }

        for callback in self.pre_publish_callbacks:
            try:
                message = yield callback(message)
            except Exception as err:
                logger.exception(err)
            else:
                if message is None:
                    raise Return((None, None))

        raise Return((message, None))

    @coroutine
    def process_publish(self, project, params, allowed_namespaces=None, client=None):
        """
        Publish message into appropriate channel.
        """
        if allowed_namespaces is None:
            project_namespaces, error = yield self.structure.get_project_namespaces(project)
            if error:
                raise Return((None, error))

            allowed_namespaces = dict((x['name'], x) for x in project_namespaces)

        message, error = yield self.prepare_message(
            project, allowed_namespaces, params, client
        )
        if error:
            raise Return((None, error))

        if not message:
            # message was discarded
            raise Return((True, None))

        # publish prepared message
        result, error = yield self.publish_message(
            message, allowed_namespaces
        )
        if error:
            raise Return((None, error))

        for callback in self.post_publish_callbacks:
            try:
                yield callback(message)
            except Exception as err:
                logger.exception(err)

        raise Return((True, None))

    @coroutine
    def process_history(self, project, params):
        """
        Return a list of last messages sent into channel.
        """
        project_id = project['_id']

        namespace_name = params.get('namespace')
        namespace, error = yield self.structure.get_namespace_by_name(
            project, namespace_name
        )
        if error:
            raise Return((None, error))
        if not namespace:
            raise Return((None, self.NAMESPACE_NOT_FOUND))
        namespace_name = namespace['name']

        channel = params.get("channel")
        message = {
            "namespace": namespace_name,
            "channel": channel,
            "data": []
        }
        data, error = yield self.state.get_history(project_id, namespace_name, channel)
        if data:
            message['data'] = data
        raise Return((message, error))

    @coroutine
    def process_presence(self, project, params):
        """
        Return current presence information for channel.
        """
        project_id = project['_id']

        namespace_name = params.get('namespace')
        namespace, error = yield self.structure.get_namespace_by_name(
            project, namespace_name
        )
        if error:
            raise Return((None, error))
        if not namespace:
            raise Return((None, self.NAMESPACE_NOT_FOUND))
        namespace_name = namespace['name']

        channel = params.get("channel")
        message = {
            "namespace": namespace_name,
            "channel": channel,
            "data": {}
        }
        data, error = yield self.state.get_presence(project_id, namespace_name, channel)
        if data:
            message['data'] = data
        raise Return((message, error))

    @coroutine
    def process_unsubscribe(self, project, params):
        """
        Unsubscribe user from channels.
        """
        params["project"] = project
        message = {
            'app_id': self.uid,
            'method': 'unsubscribe',
            'params': params
        }

        # handle on this node
        result, error = yield self.handle_unsubscribe(params)

        # send to other nodes
        self.send_control_message(message)

        raise Return((result, error))

    @coroutine
    def process_dump_structure(self, project, params):

        projects, error = yield self.structure.project_list()
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))

        namespaces, error = yield self.structure.namespace_list()
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))

        data = {
            "projects": projects,
            "namespaces": namespaces
        }
        raise Return((data, None))

    @coroutine
    def process_project_list(self, project, params):
        projects, error = yield self.structure.project_list()
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        raise Return((projects, None))

    @coroutine
    def process_project_get(self, project, params):
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))
        raise Return((project, None))

    @coroutine
    def process_project_by_name(self, project, params):
        project, error = yield self.structure.get_project_by_name(
            params.get("name")
        )
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))
        raise Return((project, None))

    @coroutine
    def process_project_create(self, project, params, error_form=False):

        form = ProjectForm(params)

        if form.validate():
            existing_project, error = yield self.structure.get_project_by_name(
                form.name.data
            )
            if error:
                raise Return((None, self.INTERNAL_SERVER_ERROR))

            if existing_project:
                form.name.errors.append(self.DUPLICATE_NAME)
                if error_form:
                    raise Return((None, form))
                raise Return((None, form.errors))
            else:
                project, error = yield self.structure.project_create(
                    **form.data
                )
                if error:
                    raise Return((None, self.INTERNAL_SERVER_ERROR))
                raise Return((project, None))
        else:
            if error_form:
                raise Return((None, form))
            raise Return((None, form.errors))

    @coroutine
    def process_project_edit(self, project, params, error_form=False):
        """
        Edit project namespace.
        """
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))

        if "name" not in params:
            params["name"] = project["name"]

        namespaces, error = yield self.structure.get_project_namespaces(project)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))

        namespace_choices = [(x['_id'], x['name']) for x in namespaces]
        namespace_choices.insert(0, ('', ''))
        form = ProjectForm(params, namespace_choices=namespace_choices)

        if form.validate():

            if "name" in params and params["name"] != project["name"]:

                existing_project, error = yield self.structure.get_project_by_name(
                    params["name"]
                )
                if error:
                    raise Return((None, self.INTERNAL_SERVER_ERROR))
                if existing_project:
                    form.name.errors.append(self.DUPLICATE_NAME)
                    if error_form:
                        raise Return((None, form))
                    raise Return((None, form.errors))

            updated_project = project.copy()
            updated_project.update(form.data)
            project, error = yield self.structure.project_edit(
                project, **updated_project
            )
            if error:
                raise Return((None, self.INTERNAL_SERVER_ERROR))
            raise Return((project, None))
        else:
            if error_form:
                raise Return((None, form))
            raise Return((None, form.errors))

    @coroutine
    def process_project_delete(self, project, params):
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))
        result, error = yield self.structure.project_delete(project)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        raise Return((True, None))

    @coroutine
    def process_regenerate_secret_key(self, project, params):
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))
        result, error = yield self.structure.regenerate_project_secret_key(project)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        raise Return((result, None))

    @coroutine
    def process_namespace_list(self, project, params):
        """
        Return a list of all namespaces for project.
        """
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))
        namespaces, error = yield self.structure.get_project_namespaces(project)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        raise Return((namespaces, None))

    @coroutine
    def process_namespace_get(self, project, params):
        """
        Return a list of all namespaces for project.
        """
        namespace_id = params.get('_id')
        namespace, error = yield self.structure.get_namespace_by_id(namespace_id)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not namespace:
            raise Return((None, self.NAMESPACE_NOT_FOUND))
        raise Return((namespace, None))

    @coroutine
    def process_namespace_by_name(self, project, params):
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))

        namespace, error = yield self.structure.get_namespace_by_name(
            project, params.get("name")
        )
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not namespace:
            raise Return((None, self.NAMESPACE_NOT_FOUND))
        raise Return((namespace, None))

    @coroutine
    def process_namespace_create(self, project, params, error_form=False):
        """
        Create new namespace in project or update if already exists.
        """
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))

        form = NamespaceForm(params)

        if form.validate():
            existing_namespace, error = yield self.structure.get_namespace_by_name(
                project, form.name.data
            )
            if error:
                raise Return((None, self.INTERNAL_SERVER_ERROR))

            if existing_namespace:
                form.name.errors.append(self.DUPLICATE_NAME)
                if error_form:
                    raise Return((None, form))
                raise Return((None, form.errors))
            else:
                namespace, error = yield self.structure.namespace_create(
                    project, **form.data
                )
                if error:
                    raise Return((None, self.INTERNAL_SERVER_ERROR))
                raise Return((namespace, None))
        else:
            if error_form:
                raise Return((None, form))
            raise Return((None, form.errors))

    @coroutine
    def process_namespace_edit(self, project, params, error_form=False):
        """
        Edit project namespace.
        """
        namespace, error = yield self.structure.get_namespace_by_id(
            params.pop('_id')
        )
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))

        if not namespace:
            raise Return((None, self.NAMESPACE_NOT_FOUND))

        if not project:
            project, error = yield self.structure.get_project_by_id(
                namespace['project_id']
            )
            if error:
                raise Return((None, self.INTERNAL_SERVER_ERROR))
            if not project:
                raise Return((None, self.PROJECT_NOT_FOUND))

        if "name" not in params:
            params["name"] = namespace["name"]

        form = NamespaceForm(params)

        if form.validate():

            if "name" in params and params["name"] != namespace["name"]:

                existing_namespace, error = yield self.structure.get_namespace_by_name(
                    project, params["name"]
                )
                if error:
                    raise Return((None, self.INTERNAL_SERVER_ERROR))
                if existing_namespace:
                    form.name.errors.append(self.DUPLICATE_NAME)
                    if error_form:
                        raise Return((None, form))
                    raise Return((None, form.errors))

            updated_namespace = namespace.copy()
            updated_namespace.update(form.data)
            namespace, error = yield self.structure.namespace_edit(
                namespace, **updated_namespace
            )
            if error:
                raise Return((None, self.INTERNAL_SERVER_ERROR))
            raise Return((namespace, None))
        else:
            if error_form:
                raise Return((None, form))
            raise Return((None, form.errors))

    @coroutine
    def process_namespace_delete(self, project, params):
        """
        Delete project namespace.
        """
        namespace_id = params["_id"]

        existing_namespace, error = yield self.structure.get_namespace_by_id(namespace_id)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not existing_namespace:
            raise Return((None, self.NAMESPACE_NOT_FOUND))

        result, error = yield self.structure.namespace_delete(namespace_id)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        raise Return((True, None))
