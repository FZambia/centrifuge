# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import six
import uuid
import time
from functools import partial

import zmq
from zmq.eventloop.zmqstream import ZMQStream

import tornado.web
import tornado.ioloop
from tornado.gen import coroutine, Return
from tornado.escape import json_decode, json_encode
from tornado.escape import utf8

from . import utils
from .structure import Structure
from .state import State
from .log import logger

import socket


# separate important parts of channel name by this
CHANNEL_NAME_SEPARATOR = ':'


# add sequence of symbols to the end of each channel name to
# prevent name overlapping
CHANNEL_SUFFIX = '>>>'


# in seconds, client's send presence ping to Redis once in this interval
DEFAULT_PRESENCE_PING_INTERVAL = 25

# in seconds, how long we must consider presence info valid after
# receiving presence ping
DEFAULT_PRESENCE_EXPIRE_INTERVAL = 60


def publish(stream, channel, message):
    """
    Publish message into channel of stream.
    """
    to_publish = [utf8(channel), utf8(message)]
    stream.send_multipart(to_publish)


def create_subscription_name(project_id, namespace, channel):
    """
    Create subscription name to catch messages from specific
    project, namespace and channel.
    """
    return str(CHANNEL_NAME_SEPARATOR.join([
        project_id,
        namespace,
        channel,
        CHANNEL_SUFFIX
    ]))


# channel for administrative interface - watch for messages travelling around.
ADMIN_CHANNEL = '_admin' + CHANNEL_SUFFIX


# channel for sharing commands among all nodes.
CONTROL_CHANNEL = '_control' + CHANNEL_SUFFIX


class Response(object):

    def __init__(self, uid=None, method=None, params=None, error=None, body=None):
        self.uid = uid
        self.method = method
        self.params = params
        self.error = error
        self.body = body

    def as_message(self):
        return {
            'uid': self.uid,
            'method': self.method,
            'params': self.params,
            'error': self.error,
            'body': self.body
        }


class Application(tornado.web.Application):

    # milliseconds
    PING_INTERVAL = 5000

    # seconds
    PING_MAX_DELAY = 10

    # milliseconds
    PING_REVIEW_INTERVAL = 10000

    INTERNAL_SERVER_ERROR = 'internal server error'

    NAMESPACE_NOT_FOUND = 'namespace not found'

    def __init__(self, *args, **kwargs):

        self.zmq_context = zmq.Context()

        # create unique uid for this application
        self.uid = uuid.uuid4().hex

        # initialize dict to keep admin connections
        self.admin_connections = {}

        # initialize dict to keep client's connections
        self.connections = {}

        # dict to keep ping from nodes
        # key - node address, value - timestamp of last ping
        self.nodes = {}

        # application structure (projects, namespaces etc)
        self.structure = None

        # initialize dict to keep channel presence
        self.presence = {}

        # initialize dict to keep channel history
        self.history = {}

        # initialize dict to keep back-off information for projects
        self.back_off = {}

        self.pre_publish_callbacks = []

        # initialize tornado's application
        super(Application, self).__init__(*args, **kwargs)

    def initialize(self):
        self.init_callbacks()
        self.init_structure()
        self.init_sockets()
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
        state_config = config.get("state", None)
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

    def init_sockets(self):
        """
        Routine to create all application-wide ZeroMQ sockets.
        """
        options = self.settings['options']

        self.zmq_pub_sub_proxy = options.zmq_pub_sub_proxy

        # create PUB socket to publish instance events into it
        publish_socket = self.zmq_context.socket(zmq.PUB)
        # do not try to send messages after closing
        publish_socket.setsockopt(zmq.LINGER, 0)

        if self.zmq_pub_sub_proxy:
            # application started with XPUB/XSUB proxy
            self.zmq_xsub = options.zmq_xsub
            publish_socket.connect(self.zmq_xsub)
        else:
            # application started without XPUB/XSUB proxy
            if options.zmq_pub_port_shift:
                # calculate zmq pub port number
                zmq_pub_port = options.port + options.zmq_pub_port_shift
            else:
                zmq_pub_port = options.zmq_pub_port

            self.zmq_pub_port = zmq_pub_port

            publish_socket.bind(
                "tcp://%s:%s" % (options.zmq_pub_listen, str(self.zmq_pub_port))
            )

        # wrap pub socket into ZeroMQ stream
        self.pub_stream = ZMQStream(publish_socket)

        # create SUB socket listening to all events from all app instances
        subscribe_socket = self.zmq_context.socket(zmq.SUB)

        if self.zmq_pub_sub_proxy:
            # application started with XPUB/XSUB proxy
            self.zmq_xpub = options.zmq_xpub
            subscribe_socket.connect(self.zmq_xpub)
        else:
            # application started without XPUB/XSUB proxy
            self.zmq_sub_address = options.zmq_sub_address
            for address in self.zmq_sub_address:
                subscribe_socket.connect(address)

        subscribe_socket.setsockopt_string(
            zmq.SUBSCRIBE,
            six.u(CONTROL_CHANNEL)
        )

        def listen_control_channel():
            # wrap sub socket into ZeroMQ stream and set its on_recv callback
            self.sub_stream = ZMQStream(subscribe_socket)
            self.sub_stream.on_recv(self.handle_control_message)

        tornado.ioloop.IOLoop.instance().add_callback(
            listen_control_channel
        )

    def init_callbacks(self):
        """
        Fill custom callbacks with callable objects provided in config.
        """
        config = self.settings['config']
        pre_publish_callbacks = config.get('pre_publish_callbacks', [])

        for callable_path in pre_publish_callbacks:
            callback = utils.namedAny(callable_path)
            self.pre_publish_callbacks.append(callback)

    def send_ping(self, message):
        publish(self.pub_stream, CONTROL_CHANNEL, message)

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
        options = self.settings['options']
        address = '%s:%s' % (
            socket.gethostbyname(socket.gethostname()),
            options.port
        )
        message = {
            'app_id': self.uid,
            'method': 'ping',
            'params': {'address': address}
        }
        send_ping = partial(publish, self.pub_stream, CONTROL_CHANNEL, json_encode(message))
        ping = tornado.ioloop.PeriodicCallback(send_ping, self.PING_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, ping.start
        )

        review_ping = tornado.ioloop.PeriodicCallback(self.review_ping, self.PING_REVIEW_INTERVAL)
        tornado.ioloop.IOLoop.instance().add_timeout(
            self.PING_INTERVAL, review_ping.start
        )

    def send_control_message(self, message):
        publish(self.pub_stream, CONTROL_CHANNEL, message)

    @coroutine
    def handle_control_message(self, multipart_message):
        """
        Handle control message.
        """
        # extract actual message
        message = multipart_message[1]

        message = json_decode(message)

        app_id = message.get("app_id")
        method = message.get("method")
        params = message.get("params")

        if app_id and app_id == self.uid:
            # application id must be set when we don't want to do
            # make things twice for the same application. Setting
            # app_id means that we don't want to process control
            # message when it is appear in application instance if
            # application uid matches app_id
            raise Return((True, None))

        func = getattr(self, 'handle_%s' % method, None)
        if not func:
            raise Return((None, 'method not found'))

        result, error = yield func(params)
        raise Return((result, error))

    @coroutine
    def handle_ping(self, params):
        self.nodes[params.get('address')] = time.time()

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

        namespaces, error = yield self.structure.get_project_namespaces(project)
        if error:
            raise Return((None, error))

        namespaces = dict(
            (x['name'], x) for x in namespaces
        )

        namespace = namespaces.get(namespace_name, None)
        if not namespace:
            # namespace does not exist
            raise Return((True, None))

        for uid, connection in six.iteritems(user_connections):

            if not namespace_name and not channel:
                # unsubscribe from all channels
                for cat, channels in six.iteritems(connection.channels):
                    for chan in channels:
                        channel_to_unsubscribe = create_subscription_name(
                            project_id, namespace_name, chan
                        )
                        connection.sub_stream.setsockopt_string(
                            zmq.UNSUBSCRIBE,
                            six.u(channel_to_unsubscribe)
                        )

                connection.channels = {}

            elif namespace_name and not channel:
                # unsubscribe from all channels in namespace
                for cat, channels in six.iteritems(connection.channels):
                    if namespace_name != cat:
                        continue
                    for chan in channels:
                        channel_to_unsubscribe = create_subscription_name(
                            project_id, namespace_name, chan
                        )
                        connection.sub_stream.setsockopt_string(
                            zmq.UNSUBSCRIBE,
                            six.u(channel_to_unsubscribe)
                        )
                try:
                    del connection.channels[namespace_name]
                except KeyError:
                    pass
                raise Return((True, None))

            else:
                # unsubscribe from certain channel
                channel_to_unsubscribe = create_subscription_name(
                    project_id, namespace_name, channel
                )

                connection.sub_stream.setsockopt_string(
                    zmq.UNSUBSCRIBE,
                    six.u(channel_to_unsubscribe)
                )

                try:
                    del connection.channels[namespace_name][channel]
                except KeyError:
                    pass

        raise Return((True, None))

    @coroutine
    def handle_update_structure(self, params):
        """
        Handle request to update structure.
        """
        result, error = yield self.structure.update()
        raise Return((result, error))

    @coroutine
    def handle_publish(self, params):
        """
        Handle publishing new message.
        """
        pass

    @coroutine
    def process_call(self, project, method, params):
        """
        Process HTTP call. It can be new message publishing or
        new command.
        """
        assert isinstance(project, dict)

        handle_func = None

        if method == "publish":
            handle_func = self.process_publish
        elif method == "presence":
            handle_func = self.process_presence
        elif method == "history":
            handle_func = self.process_history

        if handle_func:
            result, error = yield handle_func(project, params)
            raise Return((result, error))

        params["project"] = project
        to_publish = {
            "method": method,
            "params": params
        }
        publish(
            self.pub_stream,
            CONTROL_CHANNEL,
            json_encode(to_publish)
        )
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
            publish(self.pub_stream, ADMIN_CHANNEL, message)

        # send to event channel
        subscription_name = create_subscription_name(
            project_id, namespace_name, channel
        )

        publish(self.pub_stream, subscription_name, message)

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
            # event stored successfully and we can make callbacks
            result, error = yield self.publish_message(
                message, allowed_namespaces
            )
            if error:
                raise Return((None, error))
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
        data, error = yield self.state.get_history(project_id, namespace_name, channel)
        raise Return((data, error))

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
        data, error = yield self.state.get_presence(project_id, namespace_name, channel)
        raise Return((data, error))