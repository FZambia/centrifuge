# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import six
import uuid
import time
import socket
from functools import partial

import tornado.web
import tornado.ioloop
from tornado.gen import coroutine, Return

try:
    from urllib import urlencode
except ImportError:
    # python 3
    # noinspection PyUnresolvedReferences
    from urllib.parse import urlencode

from jsonschema import validate, ValidationError

from centrifuge import utils
from centrifuge.log import logger
from centrifuge.metrics import Collector, Exporter
from centrifuge.response import Response, MultiResponse
from centrifuge.schema import req_schema, server_api_schema
from centrifuge.structure import validate_and_prepare_project_structure, structure_to_dict


def get_address():
    try:
        address = socket.gethostname()
    except Exception as err:
        logger.warning(err)
        address = "?"
    return address


class Application(tornado.web.Application):

    PRIVATE_CHANNEL_PREFIX = "$"

    NAMESPACE_CHANNEL_BOUNDARY = ":"

    USER_CHANNEL_BOUNDARY = "#"

    USER_CHANNEL_SEPARATOR = ','

    # in milliseconds, how often this application will send ping message
    PING_INTERVAL = 5000

    # in seconds
    PING_MAX_DELAY = 10

    # in milliseconds, how often application will remove stale ping information
    PING_REVIEW_INTERVAL = 10000

    # maximum length of channel name
    MAX_CHANNEL_LENGTH = 255

    # maximum number of messages in single admin API request
    ADMIN_API_MESSAGE_LIMIT = 100

    # maximum number of messages in single client API request
    CLIENT_API_MESSAGE_LIMIT = 100

    # time in seconds to pause before closing expired connection
    # to get client a chance to refresh connection
    EXPIRED_CONNECTION_CLOSE_DELAY = 10

    # default metrics export interval in seconds
    METRICS_EXPORT_INTERVAL = 10

    # when active no authentication required at all when connecting to Centrifuge,
    # this simplified mode suitable for demonstration or personal usage
    INSECURE = False

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

        # dictionary to keep node state and stats
        self.nodes = {}

        # application structure (projects, namespaces etc)
        self.structure = None

        # application structure transformed to a dictionary to speed up lookups
        self.structure_dict = None

        # application engine
        self.engine = None

        # list of coroutines that must be done before message publishing
        self.pre_publish_callbacks = []

        # list of coroutines that must be done after message publishing
        self.post_publish_callbacks = []

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

        # this Application has lots of default class-level
        # attributes that can be updated using configuration file
        self.override_application_settings_from_config()

        self.started = int(time.time())

    def initialize(self):
        self.init_callbacks()
        self.init_structure()
        self.init_engine()
        self.init_ping()
        self.init_metrics()

    @property
    def config(self):
        return self.settings.get("config", {})

    def override_application_settings_from_config(self):
        config = self.config

        private_channel_prefix = config.get('private_channel_prefix')
        if private_channel_prefix:
            self.PRIVATE_CHANNEL_PREFIX = private_channel_prefix

        user_channel_boundary = config.get('user_channel_boundary')
        if user_channel_boundary:
            self.USER_CHANNEL_BOUNDARY = user_channel_boundary

        namespace_channel_boundary = config.get('namespace_channel_boundary')
        if namespace_channel_boundary:
            self.NAMESPACE_CHANNEL_BOUNDARY = namespace_channel_boundary

        ping_interval = config.get('node_ping_interval')
        if ping_interval:
            self.PING_INTERVAL = ping_interval

        ping_max_delay = config.get('ping_max_delay')
        if ping_max_delay:
            self.PING_MAX_DELAY = ping_max_delay

        max_channel_length = config.get('max_channel_length')
        if max_channel_length:
            self.MAX_CHANNEL_LENGTH = max_channel_length

        admin_api_message_limit = config.get('admin_api_message_limit')
        if admin_api_message_limit:
            self.ADMIN_API_MESSAGE_LIMIT = admin_api_message_limit

        client_api_message_limit = config.get('client_api_message_limit')
        if client_api_message_limit:
            self.CLIENT_API_MESSAGE_LIMIT = client_api_message_limit

        expired_connection_close_delay = config.get('expired_connection_close_delay')
        if expired_connection_close_delay:
            self.EXPIRED_CONNECTION_CLOSE_DELAY = expired_connection_close_delay

        insecure = config.get('insecure')
        if insecure:
            self.INSECURE = insecure

        if self.INSECURE:
            logger.warn("Centrifuge started in INSECURE mode")

    def init_structure(self):
        """
        Validate and initialize structure
        """
        config = self.config
        projects = config.get("projects")
        if not projects:
            raise Exception("projects required")
        validate_and_prepare_project_structure(projects)
        self.structure = projects
        self.structure_dict = structure_to_dict(projects)

    def init_engine(self):
        """
        Initialize engine.
        """
        tornado.ioloop.IOLoop.instance().add_callback(self.engine.initialize)

    def init_callbacks(self):
        """
        Fill custom callbacks with callable objects provided in config.
        """
        config = self.config

        pre_publish_callbacks = config.get('pre_publish_callbacks', [])
        for callable_path in pre_publish_callbacks:
            callback = utils.namedAny(callable_path)
            self.pre_publish_callbacks.append(callback)

        post_publish_callbacks = config.get('post_publish_callbacks', [])
        for callable_path in post_publish_callbacks:
            callback = utils.namedAny(callable_path)
            self.post_publish_callbacks.append(callback)

    def init_metrics(self):
        """
        Initialize metrics collector - different counters, timers in
        Centrifuge which then will be exported into web interface, log or
        Graphite.
        """
        config = self.config
        metrics_config = config.get('metrics', {})

        self.log_metrics = metrics_config.get('log', False)
        self.graphite_metrics = metrics_config.get('graphite', False)

        if not self.log_metrics and not self.graphite_metrics:
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

        if self.log_metrics:
            logger.info(metrics)

        if self.graphite_metrics:
            self.exporter.export(metrics)

    @property
    def name(self):
        if self.settings['options'].name:
            return self.settings['options'].name
        return self.address.replace(".", "_") + '_' + str(self.settings['options'].port)

    @coroutine
    def send_ping(self, publish=True):

        params = {
            'uid': self.uid,
            'name': self.name,
            'clients': self.get_clients_count(),
            'unique': self.get_unique_clients_count(),
            'channels': self.get_channels_count(),
            'started': self.started
        }

        yield self.handle_ping(params)

        if not publish:
            return

        message = {
            'app_id': self.uid,
            'method': 'ping',
            'params': params
        }
        self.engine.publish_control_message(message)

    def review_ping(self):
        """
        Remove outdated information about other nodes.
        """
        now = time.time()
        outdated = []
        for node, params in self.nodes.items():
            updated = params["updated"]
            if now - updated > self.PING_MAX_DELAY:
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
        ping = tornado.ioloop.PeriodicCallback(self.send_ping, self.PING_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, ping.start
        )
        self.send_ping(publish=False)

        review_ping = tornado.ioloop.PeriodicCallback(self.review_ping, self.PING_REVIEW_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, review_ping.start
        )

    def get_clients_count(self):
        return sum(len(u) for v in six.itervalues(self.connections) for u in six.itervalues(v))

    def get_unique_clients_count(self):
        return sum(len(v) for v in six.itervalues(self.connections))

    def get_channels_count(self):
        return len(self.engine.subscriptions)

    def get_node_gauges(self):
        gauges = {
            'channels': self.get_channels_count(),
            'clients': self.get_clients_count(),
            'unique_clients': self.get_unique_clients_count(),
        }
        return gauges

    def add_connection(self, project_key, user, uid, client):
        """
        Register new client's connection.
        """
        if project_key not in self.connections:
            self.connections[project_key] = {}
        if user not in self.connections[project_key]:
            self.connections[project_key][user] = {}

        self.connections[project_key][user][uid] = client

    def remove_connection(self, project_key, user, uid):
        """
        Remove client's connection
        """
        try:
            del self.connections[project_key][user][uid]
        except KeyError:
            pass

        if project_key in self.connections and user in self.connections[project_key]:
            # clean connections
            if self.connections[project_key][user]:
                return
            try:
                del self.connections[project_key][user]
            except KeyError:
                pass
            if self.connections[project_key]:
                return
            try:
                del self.connections[project_key]
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

    def get_project(self, project_name):
        """
        Project settings can change during client's connection.
        Every time we need project - we must extract actual
        project data from structure.
        """
        return self.structure_dict.get(project_name)

    def extract_namespace_name(self, channel):
        """
        Get namespace name from channel name
        """
        if channel.startswith(self.PRIVATE_CHANNEL_PREFIX):
            # cut private channel prefix from beginning
            channel = channel[len(self.PRIVATE_CHANNEL_PREFIX):]

        if self.NAMESPACE_CHANNEL_BOUNDARY in channel:
            # namespace:rest_of_channel
            namespace_name = channel.split(self.NAMESPACE_CHANNEL_BOUNDARY, 1)[0]
        else:
            namespace_name = None

        return namespace_name

    def get_allowed_users(self, channel):
        return channel.rsplit(self.USER_CHANNEL_BOUNDARY, 1)[1].split(self.USER_CHANNEL_SEPARATOR)

    def is_channel_private(self, channel):
        return channel.startswith(self.PRIVATE_CHANNEL_PREFIX)

    def get_namespace(self, project, channel):

        namespace_name = self.extract_namespace_name(channel)

        if not namespace_name:
            # no namespace in channel name - use project options
            # as namespace options
            return project

        return project.get("namespaces", {}).get(namespace_name)

    @coroutine
    def handle_ping(self, params):
        """
        Ping message received.
        """
        params['updated'] = time.time()
        self.nodes[params.get('uid')] = params
        raise Return((True, None))

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe message received - unsubscribe client from certain channels.
        """
        project = params.get("project")
        user = params.get("user")
        channel = params.get("channel", None)

        project_name = project['name']

        # try to find user's connection
        user_connections = self.connections.get(project_name, {}).get(user, {})
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

        project_name = project['name']

        # try to find user's connection
        user_connections = self.connections.get(project_name, {}).get(user, {})
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
        pass

    @coroutine
    def process_api_data(self, project, data):
        multi_response = MultiResponse()

        if isinstance(data, dict):
            # single object request
            response = yield self.process_api_object(data, project)
            multi_response.add(response)
        elif isinstance(data, list):
            # multiple object request
            if len(data) > self.ADMIN_API_MESSAGE_LIMIT:
                raise Return((None, "admin API message limit exceeded (received {0} messages)".format(len(data))))

            for obj in data:
                response = yield self.process_api_object(obj, project)
                multi_response.add(response)
        else:
            raise Return((None, "data not an array or object"))

        raise Return((multi_response, None))

    @coroutine
    def process_api_object(self, obj, project):

        response = Response()

        try:
            validate(obj, req_schema)
        except ValidationError as e:
            response.error = str(e)
            raise Return(response)

        method = obj.get("method")
        params = obj.get("params")

        response.method = method

        schema = server_api_schema

        if method not in schema:
            response.error = self.METHOD_NOT_FOUND
        else:
            try:
                validate(params, schema[method])
            except ValidationError as e:
                response.error = str(e)
            else:
                result, error = yield self.process_call(
                    project, method, params
                )
                response.body = result
                response.error = error

        raise Return(response)

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
        project_name = project['name']
        channel = message['channel']

        namespace = self.get_namespace(project, channel)
        if not namespace:
            raise Return((False, self.NAMESPACE_NOT_FOUND))

        if namespace['watch']:
            # send to admin channel
            self.engine.publish_admin_message({
                "method": "message",
                "body": {
                    "project": project_name,
                    "message": message
                }
            })

        # send to event channel
        subscription_key = self.engine.get_subscription_key(
            project_name, channel
        )

        self.engine.publish_message(subscription_key, message)

        history_size = namespace['history_size']
        history_lifetime = namespace['history_lifetime']
        if history_size > 0 and history_lifetime > 0:
            yield self.engine.add_history_message(
                project_name, channel, message,
                history_size=history_size,
                history_lifetime=history_lifetime
            )

        if self.collector:
            self.collector.incr('messages')

        raise Return((True, None))

    @coroutine
    def prepare_message(self, project, params, info):
        """
        Prepare message before actual publishing.
        """
        channel = params.get('channel')
        if not channel:
            raise Return((None, None))

        data = params.get('data', None)

        message = {
            'uid': uuid.uuid4().hex,
            'timestamp': int(time.time()),
            'info': info,
            'channel': channel,
            'data': data
        }

        for callback in self.pre_publish_callbacks:
            try:
                message = yield callback(project["name"], message)
            except Exception as err:
                logger.exception(err)
            else:
                if message is None:
                    raise Return((None, None))

        raise Return((message, None))

    @coroutine
    def process_publish(self, project, params, info=None):
        """
        Publish message into appropriate channel.
        """
        message, error = yield self.prepare_message(
            project, params, info
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
                yield callback(project["name"], message)
            except Exception as err:
                logger.exception(err)

        raise Return((True, None))

    @coroutine
    def process_history(self, project, params):
        """
        Return a list of last messages sent into channel.
        """
        project_name = project['name']
        channel = params.get("channel")
        data, error = yield self.engine.get_history(project_name, channel)
        if error:
            raise Return(([], self.INTERNAL_SERVER_ERROR))
        raise Return((data, None))

    @coroutine
    def process_presence(self, project, params):
        """
        Return current presence information for channel.
        """
        project_name = project['name']
        channel = params.get("channel")
        data, error = yield self.engine.get_presence(project_name, channel)
        if error:
            raise Return(({}, self.INTERNAL_SERVER_ERROR))
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
