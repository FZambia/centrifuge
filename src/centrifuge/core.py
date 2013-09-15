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
from tornado.escape import json_encode

from . import utils
from .structure import Structure
from .state import State
from .log import logger
from .pubsub import ZmqPubSub, CONTROL_CHANNEL, ADMIN_CHANNEL


# in seconds, client's send presence ping to Redis once in this interval
DEFAULT_PRESENCE_PING_INTERVAL = 25


# in seconds, how long we must consider presence info valid after
# receiving presence ping
DEFAULT_PRESENCE_EXPIRE_INTERVAL = 60


class Application(tornado.web.Application):

    # milliseconds
    PING_INTERVAL = 5000

    # seconds
    PING_MAX_DELAY = 10

    # milliseconds
    PING_REVIEW_INTERVAL = 10000

    PERMISSION_DENIED = 'permission denied'

    INTERNAL_SERVER_ERROR = 'internal server error'

    PROJECT_NOT_FOUND = 'project not found'

    NAMESPACE_NOT_FOUND = 'namespace not found'

    def __init__(self, *args, **kwargs):

        # create unique uid for this application
        self.uid = uuid.uuid4().hex

        self.pubsub = None

        # initialize dict to keep administrator's connections
        self.admin_connections = {}

        # initialize dict to keep client's connections
        self.connections = {}

        # dict to keep ping from nodes
        # key - node address, value - timestamp of last ping
        self.nodes = {}

        # application structure (projects, namespaces etc)
        self.structure = None

        # initialize dict to keep back-off information for projects
        self.back_off = {}

        self.pre_publish_callbacks = []

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
        config = self.settings['config']
        state_config = config.get("state", {})
        self.presence_ping_interval = state_config.get(
            'presence_ping_interval', DEFAULT_PRESENCE_PING_INTERVAL
        )*1000
        if not state_config:
            self.state = State(fake=True)
        else:
            host = state_config.get("host", "localhost")
            port = state_config.get("port", 6379)
            self.state = State(
                host=host,
                port=port,
                presence_timeout=state_config.get(
                    "presence_expire_interval",
                    DEFAULT_PRESENCE_EXPIRE_INTERVAL
                )
            )
            tornado.ioloop.IOLoop.instance().add_callback(self.state.connect)

    def init_pubsub(self):
        """
        Routine to create all application-wide ZeroMQ sockets.
        """
        self.pubsub = ZmqPubSub(self)

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

    def send_ping(self, message):
        self.pubsub.publish(CONTROL_CHANNEL, message)

    def review_ping(self):
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

        message = {
            'app_id': self.uid,
            'method': 'ping',
            'params': {'uid': self.uid}
        }
        send_ping = partial(self.pubsub.publish, CONTROL_CHANNEL, json_encode(message))
        ping = tornado.ioloop.PeriodicCallback(send_ping, self.PING_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, ping.start
        )

        review_ping = tornado.ioloop.PeriodicCallback(self.review_ping, self.PING_REVIEW_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, review_ping.start
        )

    def send_control_message(self, message):
        self.pubsub.publish(CONTROL_CHANNEL, message)

    def add_connection(self, project_id, user, uid, client):
        """
        Register client's connection.
        """
        if project_id not in self.connections:
            self.connections[project_id] = {}
        if user and user not in self.connections:
            self.connections[project_id][user] = {}
        if user:
            self.connections[project_id][user][uid] = client

    def remove_connection(self, project_id, user, uid):
        """
        Unregister client's connection
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
        Unregister administrator's connection.
        """
        try:
            del self.admin_connections[uid]
        except KeyError:
            pass

    @coroutine
    def handle_ping(self, params):
        self.nodes[params.get('uid')] = time.time()

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe client from certain channels.
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
        Handle request to update structure.
        """
        result, error = yield self.structure.update()
        raise Return((result, error))

    @coroutine
    def process_call(self, project, method, params):
        """
        Process HTTP call. It can be new message publishing or
        new command.
        """
        assert isinstance(project, dict)

        handle_func = getattr(self, "process_%s" % method, None)

        if handle_func:
            # noinspection PyCallingNonCallable
            result, error = yield handle_func(project, params)
            raise Return((result, error))

        params["project"] = project
        to_publish = {
            "method": method,
            "params": params
        }
        self.pubsub.publish(CONTROL_CHANNEL, json_encode(to_publish))
        result, error = True, None
        raise Return((result, error))

    @coroutine
    def publish_message(self, message, allowed_namespaces):
        """
        Publish event into PUB socket stream
        """
        project_id = message['project_id']
        namespace_name = message['namespace']
        channel = message['channel']

        message = json_encode(message)

        if allowed_namespaces[namespace_name]['is_watching']:
            # send to admin channel
            self.pubsub.publish(ADMIN_CHANNEL, message)

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
    def prepare_message(self, project, allowed_namespaces, params, client_id):
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
            raise Return(("namespace not found in allowed namespaces", None))

        message = {
            'project_id': project['_id'],
            'namespace': namespace['name'],
            'uid': uuid.uuid4().hex,
            'client_id': client_id,
            'channel': params.get('channel'),
            'data': params.get('data', None)
        }

        for callback in self.pre_publish_callbacks:
            message, error = yield callback(message)
            if error:
                raise Return((message, error))
            if message is None:
                raise Return(('message discarded', None))

        raise Return((message, None))

    @coroutine
    def process_publish(self, project, params, allowed_namespaces=None, client_id=None):

        if allowed_namespaces is None:
            project_namespaces, error = yield self.structure.get_project_namespaces(project)
            if error:
                raise Return((None, error))

            allowed_namespaces = dict((x['name'], x) for x in project_namespaces)

        message, error = yield self.prepare_message(
            project, allowed_namespaces, params, client_id
        )
        if error:
            raise Return((None, error))

        if isinstance(message, dict):
            # event prepared for publishing
            result, error = yield self.publish_message(
                message, allowed_namespaces
            )
            if error:
                raise Return((None, error))

            for callback in self.post_publish_callbacks:
                result, error = yield callback(message)
                if error:
                    logger.error(str(error))
        else:
            # message is error description
            raise Return((None, message))

        raise Return((True, None))

    @coroutine
    def process_history(self, project, params):
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

        params["project"] = project
        message = {
            'app_id': self.uid,
            'method': 'unsubscribe',
            'params': params
        }

        # handle on this node
        result, error = yield self.handle_unsubscribe(params)

        # send to other nodes
        self.send_control_message(json_encode(message))

        raise Return((result, error))
