# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import six
import zmq
from zmq.eventloop.zmqstream import ZMQStream
import tornado.web
import tornado.ioloop
from tornado.gen import coroutine
from tornado.escape import utf8, json_encode, json_decode

from centrifuge.log import logger
from centrifuge.pubsub.base import BasePubSub, ADMIN_CHANNEL, CONTROL_CHANNEL


class PubSub(BasePubSub):
    """
    This class manages application PUB/SUB logic.
    """
    NAME = 'ZeroMQ'

    def __init__(self, application):
        super(PubSub, self).__init__(application)
        self.sub_stream = None
        self.pub_stream = None
        self.zmq_context = None
        self.zmq_pub_sub_proxy = None
        self.zmq_xpub = None
        self.zmq_xsub = None
        self.zmq_pub_port = None
        self.zmq_sub_address = None

    def initialize(self):

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
        method = method or self.DEFAULT_PUBLISH_METHOD
        message["message_type"] = method
        message = json_encode(message)
        to_publish = [utf8(channel), utf8(message)]
        self.pub_stream.send_multipart(to_publish)

    @coroutine
    def dispatch_published_message(self, multipart_message):
        """
        Got message, decide what is it and dispatch into right
        application handler.
        """
        channel = multipart_message[0]
        if six.PY3:
            channel = channel.decode()

        message_data = json_decode(multipart_message[1])

        if channel == CONTROL_CHANNEL:
            yield self.handle_control_message(message_data)
        elif channel == ADMIN_CHANNEL:
            yield self.handle_admin_message(message_data)
        else:
            yield self.handle_channel_message(channel, message_data)

    def subscribe_key(self, subscription_key):
        self.sub_stream.setsockopt_string(
            zmq.SUBSCRIBE, six.u(subscription_key)
        )

    def unsubscribe_key(self, subscription_key):
        self.sub_stream.setsockopt_string(
            zmq.UNSUBSCRIBE, six.u(subscription_key)
        )

    def clean(self):
        """
        Properly close ZeroMQ sockets.
        """
        if hasattr(self, 'pub_stream') and self.pub_stream:
            self.pub_stream.close()
        if hasattr(self, 'sub_stream') and self.sub_stream:
            self.sub_stream.stop_on_recv()
            self.sub_stream.close()