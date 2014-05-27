# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import six
import uuid
import time
import socket
import json
from functools import partial

import tornado.web
import tornado.ioloop
from tornado.gen import coroutine, Return
from tornado.httpclient import AsyncHTTPClient, HTTPRequest

try:
    from urllib import urlencode
except ImportError:
    # python 3
    # noinspection PyUnresolvedReferences
    from urllib.parse import urlencode

from centrifuge import utils
from centrifuge.structure import Structure
from centrifuge.log import logger
from centrifuge.forms import NamespaceForm, ProjectForm
from centrifuge.metrics import Collector, Exporter


def get_address():
    try:
        address = socket.gethostbyname(socket.gethostname())
    except Exception as err:
        logger.warning(err)
        address = "?"
    return address


class Application(tornado.web.Application):

    USER_SEPARATOR = '#'

    NAMESPACE_SEPARATOR = ":"

    # magic fake project ID for owner API purposes.
    OWNER_API_PROJECT_ID = '_'

    # magic project param name to allow owner make API operations within project
    OWNER_API_PROJECT_PARAM = '_project'

    # in milliseconds, how often this application will send ping message
    PING_INTERVAL = 5000

    # in seconds
    PING_MAX_DELAY = 10

    # in milliseconds, how often node will send its info into admin channel
    NODE_INFO_PUBLISH_INTERVAL = 10000

    # in milliseconds, how often application will remove stale ping information
    PING_REVIEW_INTERVAL = 10000

    # maximum length of channel name
    MAX_CHANNEL_LENGTH = 255

    # maximum number of messages in single admin API request
    ADMIN_API_MESSAGE_LIMIT = 100

    # maximum number of messages in single client API request
    CLIENT_API_MESSAGE_LIMIT = 100

    # does application check expiring connections?
    CONNECTION_EXPIRE_CHECK = True

    # how often in seconds this node should check expiring connections
    CONNECTION_EXPIRE_COLLECT_INTERVAL = 3

    # how often in seconds this node should check expiring connections
    CONNECTION_EXPIRE_CHECK_INTERVAL = 6

    # default metrics export interval in seconds
    METRICS_EXPORT_INTERVAL = 10

    LIMIT_EXCEEDED = 'limit exceeded'

    UNAUTHORIZED = 'unauthorized'

    PERMISSION_DENIED = 'permission denied'

    NOT_AVAILABLE = 'not available'

    INTERNAL_SERVER_ERROR = 'internal server error'

    METHOD_NOT_FOUND = 'method not found'

    PROJECT_NOT_FOUND = 'project not found'

    NAMESPACE_NOT_FOUND = 'namespace not found'

    DUPLICATE_NAME = 'duplicate name'

    def __init__(self, *args, **kwargs):

        # create unique uid for this application
        self.uid = uuid.uuid4().hex

        # initialize dict to keep administrator's connections
        self.admin_connections = {}

        # dictionary to keep client's connections
        self.connections = {}

        # dictionary to keep ping from nodes
        self.nodes = {}

        # storage to use
        self.storage = None

        # application structure manager (projects, namespaces etc)
        self.structure = None

        # application engine
        self.engine = None

        # initialize dict to keep back-off information for projects
        self.back_off = {}

        # list of coroutines that must be done before message publishing
        self.pre_publish_callbacks = []

        # list of coroutines that must be done after message publishing
        self.post_publish_callbacks = []

        # time of last node info revision
        self.node_info_revision_time = time.time()

        # periodic task to collect expired connections
        self.periodic_connection_expire_collect = None

        # periodic task to check expired connections
        self.periodic_connection_expire_check = None

        # dictionary to keep expired connections
        self.expired_connections = {}

        # dictionary to keep new connections with expired credentials until next connection check
        self.expired_reconnections = {}

        self.address = get_address()

        # count of messages published since last node info revision
        self.messages_published = 0

        # metrics collector class instance
        self.collector = None

        # metric exporter class instance
        self.exporter = None

        # periodic task to export collected metrics
        self.periodic_metrics_export = None

        # log collected metrics
        self.log_metrics = False

        # send collected metrics into admin channel
        self.admin_metrics = True

        # export collected metrics into Graphite
        self.graphite_metrics = False

        # initialize tornado's application
        super(Application, self).__init__(*args, **kwargs)

    def initialize(self):
        self.init_callbacks()
        self.init_structure()
        self.init_engine()
        self.init_ping()
        self.init_connection_expire_check()
        self.init_metrics()

    def init_structure(self):
        """
        Initialize structure manager using settings provided
        in configuration file.
        """
        custom_settings = self.settings['config']
        self.structure = Structure(self)
        self.structure.set_storage(self.storage)

        def run_periodic_structure_update():
            # update structure periodically from database. This is necessary to be sure
            # that application has actual and correct structure information. Structure
            # updates also triggered in real-time by message passing through control channel,
            # but in rare cases those update messages can be lost because of some kind of
            # network errors
            logger.info("Structure initialized")
            self.structure.update()
            structure_update_interval = custom_settings.get('structure_update_interval', 60)
            logger.info(
                "Periodic structure update interval: {0} seconds".format(
                    structure_update_interval
                )
            )
            periodic_structure_update = tornado.ioloop.PeriodicCallback(
                self.structure.update, structure_update_interval*1000
            )
            periodic_structure_update.start()

        tornado.ioloop.IOLoop.instance().add_callback(
            partial(
                self.storage.connect,
                run_periodic_structure_update
            )
        )

    def init_engine(self):
        """
        Initialize engine.
        """
        tornado.ioloop.IOLoop.instance().add_callback(self.engine.initialize)

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

    def init_connection_expire_check(self):
        """
        Initialize periodic connection expiration check task if enabled.
        We periodically check the time of client connection expiration time
        and ask web application about these clients - are they still active in
        web application?
        """

        if not self.CONNECTION_EXPIRE_CHECK:
            return

        self.periodic_connection_expire_collect = tornado.ioloop.PeriodicCallback(
            self.collect_expired_connections,
            self.CONNECTION_EXPIRE_COLLECT_INTERVAL*1000
        )
        self.periodic_connection_expire_collect.start()

        tornado.ioloop.IOLoop.instance().add_timeout(
            time.time()+self.CONNECTION_EXPIRE_CHECK_INTERVAL,
            self.check_expired_connections
        )

    def init_metrics(self):
        """
        Initialize metrics collector - different counters, timers in
        Centrifuge which then will be exported into web interface, log or
        Graphite.
        """
        config = self.settings['config']
        metrics_config = config.get('metrics', {})

        self.admin_metrics = metrics_config.get('admin', True)
        self.log_metrics = metrics_config.get('log', False)
        self.graphite_metrics = metrics_config.get('graphite', False)

        if not self.log_metrics and not self.admin_metrics and not self.graphite_metrics:
            return

        self.collector = Collector()

        if self.graphite_metrics:

            prefix = metrics_config.get("graphite_prefix", "")
            if prefix and not prefix.endswith(Exporter.SEP):
                prefix = prefix + Exporter.SEP

            prefix += self.name

            self.exporter = Exporter(
                metrics_config["graphite_host"],
                metrics_config["graphite_port"],
                prefix=prefix
            )

        self.periodic_metrics_export = tornado.ioloop.PeriodicCallback(
            self.flush_metrics,
            metrics_config.get("interval", self.METRICS_EXPORT_INTERVAL)*1000
        )
        self.periodic_metrics_export.start()

    def flush_metrics(self):

        if not self.collector:
            return

        for key, value in six.iteritems(self.get_node_gauges()):
            self.collector.gauge(key, value)

        metrics = self.collector.get()

        if self.admin_metrics:
            self.publish_node_info(metrics)

        if self.log_metrics:
            logger.info(metrics)

        if self.graphite_metrics:
            self.exporter.export(metrics)

    @property
    def name(self):
        if self.settings['options'].name:
            return self.settings['options'].name
        return self.address.replace(".", "_") + '_' + str(self.settings['options'].port)

    def send_ping(self, ping_message):
        self.engine.publish_control_message(ping_message)

    def review_ping(self):
        """
        Remove outdated information about other nodes.
        """
        now = time.time()
        outdated = []
        for node, params in self.nodes.items():
            updated_at = params["updated_at"]
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
            'params': {
                'uid': self.uid,
                'name': self.name
            }
        }
        send_ping = partial(self.engine.publish_control_message, message)
        ping = tornado.ioloop.PeriodicCallback(send_ping, self.PING_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, ping.start
        )

        review_ping = tornado.ioloop.PeriodicCallback(self.review_ping, self.PING_REVIEW_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, review_ping.start
        )

    def get_node_gauges(self):
        gauges = {
            'channels': len(self.engine.subscriptions),
            'clients': sum(len(v) for v in six.itervalues(self.engine.subscriptions)),
            'unique_clients': sum(len(v) for v in six.itervalues(self.connections)),
        }
        return gauges

    def publish_node_info(self, metrics):
        """
        Publish information about current node into admin channel
        """
        self.engine.publish_admin_message({
            "admin": True,
            "type": "node",
            "data": {
                "uid": self.uid,
                "nodes": len(self.nodes) + 1,
                "name": self.name,
                "metrics": metrics
            }
        })

    @coroutine
    def collect_expired_connections(self):
        """
        Find all expired connections in projects to check them later.
        """
        projects, error = yield self.structure.project_list()
        if error:
            logger.error(error)
            raise Return((None, error))

        for project in projects:

            project_id = project['_id']
            expired_connections, error = yield self.collect_project_expired_connections(project)
            if error:
                logger.error(error)
                continue

            if project_id not in self.expired_connections:
                self.expired_connections[project_id] = {
                    "users": set(),
                    "checked_at": None
                }

            current_expired_connections = self.expired_connections[project_id]["users"]
            self.expired_connections[project_id]["users"] = current_expired_connections | expired_connections

        raise Return((True, None))

    @coroutine
    def collect_project_expired_connections(self, project):
        """
        Find users in project whose connections expired.
        """
        project_id = project.get("_id")
        to_return = set()
        now = time.time()
        if not project.get('connection_check') or project_id not in self.connections:
            raise Return((to_return, None))

        for user, user_connections in six.iteritems(self.connections[project_id]):

            if user == '':
                # do not collect anonymous connections
                continue

            for uid, client in six.iteritems(user_connections):
                if client.examined_at and client.examined_at + project.get("connection_lifetime", 24*365*3600) < now:
                    to_return.add(user)

        raise Return((to_return, None))

    @coroutine
    def check_expired_connections(self):
        """
        For each project ask web application about users whose connections expired.
        Close connections of deactivated users and keep valid users' connections.
        """
        projects, error = yield self.structure.project_list()
        if error:
            raise Return((None, error))

        checks = []
        for project in projects:
            if project.get('connection_check', False):
                checks.append(self.check_project_expired_connections(project))

        try:
            # run all checks in parallel
            yield checks
        except Exception as err:
            logger.error(err)

        tornado.ioloop.IOLoop.instance().add_timeout(
            time.time()+self.CONNECTION_EXPIRE_CHECK_INTERVAL,
            self.check_expired_connections
        )

        raise Return((True, None))

    @coroutine
    def check_project_expired_connections(self, project):

        now = time.time()
        project_id = project['_id']

        checked_at = self.expired_connections.get(project_id, {}).get("checked_at")
        if checked_at and (now - checked_at < project.get("connection_check_interval", 60)):
            raise Return((True, None))

        users = self.expired_connections.get(project_id, {}).get("users", {}).copy()
        if not users:
            raise Return((True, None))

        self.expired_connections[project_id]["users"] = set()

        expired_reconnect_clients = self.expired_reconnections.get(project_id, [])[:]
        self.expired_reconnections[project_id] = []

        inactive_users, error = yield self.check_users(project, users)
        if error:
            raise Return((False, error))

        self.expired_connections[project_id]["checked_at"] = now
        now = time.time()

        clients_to_disconnect = []

        if isinstance(inactive_users, list):
            # a list of inactive users received, iterate trough connections
            # destroy inactive, update active.
            if project_id in self.connections:
                for user, user_connections in six.iteritems(self.connections[project_id]):
                    for uid, client in six.iteritems(user_connections):
                        if client.user in inactive_users:
                            clients_to_disconnect.append(client)
                        elif client.user in users:
                            client.examined_at = now

        for client in clients_to_disconnect:
            yield client.send_disconnect_message("deactivated")
            yield client.close_sock()

        if isinstance(inactive_users, list):
            # now deal with users waiting for reconnect with expired credentials
            for client in expired_reconnect_clients:
                is_valid = client.user not in inactive_users
                if is_valid:
                    client.examined_at = now
                if client.connect_queue:
                    yield client.connect_queue.put(is_valid)
                else:
                    yield client.close_sock()

        raise Return((True, None))

    @staticmethod
    @coroutine
    def check_users(project, users, timeout=5):

        address = project.get("connection_check_address")
        if not address:
            logger.debug("no connection check address for project {0}".format(project['name']))
            raise Return(())

        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            address,
            method="POST",
            body=urlencode({
                'users': json.dumps(list(users))
            }),
            request_timeout=timeout
        )

        try:
            response = yield http_client.fetch(request)
        except Exception as err:
            logger.error(err)
            raise Return((None, None))
        else:
            if response.code != 200:
                raise Return((None, None))

            try:
                content = [str(x) for x in json.loads(response.body)]
            except Exception as err:
                logger.error(err)
                raise Return((None, err))

            raise Return((content, None))

    def add_connection(self, project_id, user, uid, client):
        """
        Register new client's connection.
        """
        if project_id not in self.connections:
            self.connections[project_id] = {}
        if user not in self.connections[project_id]:
            self.connections[project_id][user] = {}

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
    def get_project(self, project_id):
        """
        Project settings can change during client's connection.
        Every time we need project - we must extract actual
        project data from structure.
        """
        project, error = yield self.structure.get_project_by_id(project_id)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))
        raise Return((project, None))

    def extract_namespace_name(self, channel):
        """
        Get namespace name from channel name
        """
        if self.NAMESPACE_SEPARATOR in channel:
            # namespace:rest_of_channel
            namespace_name = channel.split(self.NAMESPACE_SEPARATOR, 1)[0]
        else:
            namespace_name = None

        return namespace_name

    @coroutine
    def get_namespace(self, project, channel):

        namespace_name = self.extract_namespace_name(channel)

        if not namespace_name:
            raise Return((project, None))

        namespace, error = yield self.structure.get_namespace_by_name(
            project, namespace_name
        )
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not namespace:
            raise Return((None, self.NAMESPACE_NOT_FOUND))
        raise Return((namespace, None))

    @coroutine
    def handle_ping(self, params):
        """
        Ping message received.
        """
        params['updated_at'] = time.time()
        self.nodes[params.get('uid')] = params

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe message received - unsubscribe client from certain channels.
        """
        project = params.get("project")
        user = params.get("user")
        channel = params.get("channel", None)

        project_id = project['_id']

        # try to find user's connection
        user_connections = self.connections.get(project_id, {}).get(user, {})
        if not user_connections:
            raise Return((True, None))

        for uid, connection in six.iteritems(user_connections):

            if not channel:
                # unsubscribe from all channels
                for chan, channel_info in six.iteritems(connection.channels):
                    yield connection.handle_unsubscribe({
                        "channel": chan
                    })
            else:
                # unsubscribe from certain channel
                yield connection.handle_unsubscribe({
                    "channel": channel
                })

        raise Return((True, None))

    @coroutine
    def handle_disconnect(self, params):
        """
        Handle disconnect message - when user deactivated in web application
        and its connections must be closed by Centrifuge by force
        """
        project = params.get("project")
        user = params.get("user")
        reason = params.get("reason", None)

        project_id = project['_id']

        # try to find user's connection
        user_connections = self.connections.get(project_id, {}).get(user, {})
        if not user_connections:
            raise Return((True, None))

        clients_to_disconnect = []

        for uid, client in six.iteritems(user_connections):
            clients_to_disconnect.append(client)

        for client in clients_to_disconnect:
            yield client.send_disconnect_message(reason=reason)
            yield client.close_sock(pause=False)

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
    def publish_message(self, project, message):
        """
        Publish event into PUB socket stream
        """
        project_id = message['project_id']
        channel = message['channel']

        namespace, error = yield self.get_namespace(project, channel)
        if error:
            raise Return((False, error))

        if namespace.get('is_watching', False):
            # send to admin channel
            self.engine.publish_admin_message(message)

        # send to event channel
        subscription_key = self.engine.get_subscription_key(
            project_id, channel
        )

        # no need in project id when sending message to clients
        del message['project_id']

        self.engine.publish_message(subscription_key, message)

        if namespace.get('history', False):
            yield self.engine.add_history_message(
                project_id, channel, message,
                history_size=namespace.get('history_size'),
                history_expire=namespace.get('history_expire', 0)
            )

        if self.collector:
            self.collector.incr('messages')

        raise Return((True, None))

    @coroutine
    def prepare_message(self, project, params, client):
        """
        Prepare message before actual publishing.
        """
        data = params.get('data', None)

        message = {
            'project_id': project['_id'],
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
    def process_publish(self, project, params, client=None):
        """
        Publish message into appropriate channel.
        """
        message, error = yield self.prepare_message(
            project, params, client
        )
        if error:
            raise Return((False, self.INTERNAL_SERVER_ERROR))

        if not message:
            # message was discarded
            raise Return((False, None))

        # publish prepared message
        result, error = yield self.publish_message(
            project, message
        )
        if error:
            raise Return((False, error))

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
        channel = params.get("channel")
        data, error = yield self.engine.get_history(project_id, channel)
        if error:
            raise Return((data, self.INTERNAL_SERVER_ERROR))
        raise Return((data, None))

    @coroutine
    def process_presence(self, project, params):
        """
        Return current presence information for channel.
        """
        project_id = project['_id']
        channel = params.get("channel")
        data, error = yield self.engine.get_presence(project_id, channel)
        if error:
            raise Return((data, self.INTERNAL_SERVER_ERROR))
        raise Return((data, None))

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
        self.engine.publish_control_message(message)

        if error:
            raise Return((result, self.INTERNAL_SERVER_ERROR))
        raise Return((result, None))

    @coroutine
    def process_disconnect(self, project, params):
        """
        Unsubscribe user from channels.
        """
        params["project"] = project
        message = {
            'app_id': self.uid,
            'method': 'disconnect',
            'params': params
        }

        # handle on this node
        result, error = yield self.handle_disconnect(params)

        # send to other nodes
        self.engine.publish_control_message(message)

        if error:
            raise Return((result, self.INTERNAL_SERVER_ERROR))
        raise Return((result, None))

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
    def process_project_edit(self, project, params, error_form=False, patch=True):
        """
        Edit project namespace.
        """
        if not project:
            raise Return((None, self.PROJECT_NOT_FOUND))

        if "name" not in params:
            params["name"] = project["name"]

        boolean_patch_data = {}
        if patch:
            boolean_patch_data = utils.get_boolean_patch_data(ProjectForm.BOOLEAN_FIELDS, params)

        form = ProjectForm(params)

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

            if patch:
                data = utils.make_patch_data(form, params)
            else:
                data = form.data.copy()

            updated_project.update(data)
            if patch:
                updated_project.update(boolean_patch_data)
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
    def process_namespace_edit(self, project, params, error_form=False, patch=True):
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
            project, error = yield self.get_project(
                namespace['project_id']
            )
            if error:
                raise Return((None, error))

        if "name" not in params:
            params["name"] = namespace["name"]

        boolean_patch_data = {}
        if patch:
            boolean_patch_data = utils.get_boolean_patch_data(NamespaceForm.BOOLEAN_FIELDS, params)

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
            if patch:
                data = utils.make_patch_data(form, params)
            else:
                data = form.data.copy()
            updated_namespace.update(data)
            if patch:
                updated_namespace.update(boolean_patch_data)
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

        result, error = yield self.structure.namespace_delete(existing_namespace)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        raise Return((True, None))
