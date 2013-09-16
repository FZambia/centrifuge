# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import six

import zmq
from zmq.eventloop.zmqstream import ZMQStream

import tornado.web
import tornado.ioloop
from tornado.gen import coroutine, Return
from tornado.escape import utf8, json_decode

from .response import Response
from .log import logger


# separate important parts of channel name by this
CHANNEL_NAME_SEPARATOR = ':'


# add sequence of symbols to the end of each channel name to
# prevent name overlapping
CHANNEL_SUFFIX = '>>>'


# channel for administrative interface - watch for messages travelling around.
ADMIN_CHANNEL = '_admin' + CHANNEL_SUFFIX


# channel for sharing commands among all nodes.
CONTROL_CHANNEL = '_control' + CHANNEL_SUFFIX


DEFAULT_PUBLISH_METHOD = 'message'


class ZmqPubSub(object):
    """
    This class manages application PUB/SUB logic.
    """
    def __init__(self, application):
        self.application = application
        self.subscriptions = {}
        self.sub_stream = None

        self.init_sockets()

    def init_sockets(self):
        self.zmq_context = zmq.Context()
        options = self.application.settings['options']

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
                zmq_pub_port = options.port - options.zmq_pub_port_shift
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

        subscribe_socket.setsockopt_string(
            zmq.SUBSCRIBE, six.u(ADMIN_CHANNEL)
        )

        def listen_socket():
            # wrap sub socket into ZeroMQ stream and set its on_recv callback
            self.sub_stream = ZMQStream(subscribe_socket)
            self.sub_stream.on_recv(self.dispatch_published_message)

        tornado.ioloop.IOLoop.instance().add_callback(
            listen_socket
        )

        if self.zmq_pub_sub_proxy:
            logger.info(
                "ZeroMQ XPUB: {0}, XSUB: {1}".format(self.zmq_xpub, self.zmq_xsub)
            )
        else:
            logger.info(
                "ZeroMQ PUB - {0}; subscribed to {1}".format(self.zmq_pub_port, self.zmq_sub_address)
            )

    def publish(self, channel, message, method=None):
        """
        Publish message into channel of stream.
        """
        method = method or DEFAULT_PUBLISH_METHOD
        to_publish = [utf8(channel), utf8(method), utf8(message)]
        self.pub_stream.send_multipart(to_publish)

    def get_subscription_key(self, project_id, namespace, channel):
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

    @coroutine
    def dispatch_published_message(self, multipart_message):
        """
        Got message, decide what is it and dispatch into right
        application handler.
        """
        channel = multipart_message[0]
        method = multipart_message[1]
        message_data = multipart_message[2]
        if six.PY3:
            message_data = message_data.decode()
        if channel == CONTROL_CHANNEL:
            yield self.handle_control_message(message_data)
        elif channel == ADMIN_CHANNEL:
            yield self.handle_admin_message(message_data)
        else:
            yield self.handle_channel_message(channel, method, message_data)

    @coroutine
    def handle_admin_message(self, message):
        for uid, connection in six.iteritems(self.application.admin_connections):
            if uid in self.application.admin_connections:
                connection.send(message)

    @coroutine
    def handle_channel_message(self, channel, method, message):
        if channel not in self.subscriptions:
            raise Return((True, None))

        response = Response(method=method, body=message)
        prepared_response = response.as_message()

        for uid, client in six.iteritems(self.subscriptions[channel]):
            if channel in self.subscriptions and uid in self.subscriptions[channel]:
                client.send(prepared_response)

    @coroutine
    def handle_control_message(self, message):
        """
        Handle control message.
        """
        message = json_decode(message)

        app_id = message.get("app_id")
        method = message.get("method")
        params = message.get("params")

        if app_id and app_id == self.application.uid:
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

    def add_subscription(self, project_id, namespace_name, channel, client):
        """
        Subscribe application on channel if necessary and register client
        to receive messages from that channel.
        """
        subscription_key = self.get_subscription_key(project_id, namespace_name, channel)
        self.sub_stream.setsockopt_string(
            zmq.SUBSCRIBE, six.u(subscription_key)
        )

        if subscription_key not in self.subscriptions:
            self.subscriptions[subscription_key] = {}

        self.subscriptions[subscription_key][client.uid] = client

    def remove_subscription(self, project_id, namespace_name, channel, client):
        """
        Unsubscribe application from channel if necessary and unregister client
        from receiving messages from that channel.
        """
        subscription_key = self.get_subscription_key(project_id, namespace_name, channel)

        try:
            del self.subscriptions[subscription_key][client.uid]
        except KeyError:
            pass

        try:
            if not self.subscriptions[subscription_key]:
                self.sub_stream.setsockopt_string(
                    zmq.UNSUBSCRIBE, six.u(subscription_key)
                )
                del self.subscriptions[subscription_key]
        except KeyError:
            pass
