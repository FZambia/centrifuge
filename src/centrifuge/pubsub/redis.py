# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import six

import toredis
from tornado.gen import coroutine, Return, Task
from tornado.escape import json_decode

from tornado.escape import json_encode

from ..response import Response
from ..log import logger


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


class PubSub(object):
    """
    This class manages application PUB/SUB logic.
    """
    def __init__(self, application):
        self.application = application
        self.subscriptions = {}
        self.client = None

    def initialize(self):

        self.subscriber = toredis.Client()

        self.publisher = toredis.Client()

        try:
            self.subscriber.connect(host="localhost", port=6379)
            self.publisher.connect(host="localhost", port=6379)
        except Exception as e:
            logger.error("error connecting to Redis server: %s" % (str(e)))

        self.subscriber.subscribe(CONTROL_CHANNEL, callback=self.dispatch_published_message)
        self.subscriber.subscribe(ADMIN_CHANNEL, callback=self.dispatch_published_message)

        logger.info("Redis PUB/SUB")

    def publish(self, channel, message, method=None):
        """
        Publish message into channel of stream.
        """
        method = method or DEFAULT_PUBLISH_METHOD
        message["message_type"] = method
        to_publish = json_encode(message)
        self.publisher.publish(channel, to_publish)

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
        if multipart_message[0] != 'message':
            return

        channel = multipart_message[1]
        message_data = multipart_message[2]
        if six.PY3:
            message_data = message_data.decode()
        if channel == CONTROL_CHANNEL:
            yield self.handle_control_message(message_data)
        elif channel == ADMIN_CHANNEL:
            yield self.handle_admin_message(message_data)
        else:
            yield self.handle_channel_message(channel, message_data)

    @coroutine
    def handle_admin_message(self, message):
        for uid, connection in six.iteritems(self.application.admin_connections):
            if uid in self.application.admin_connections:
                connection.send(message)

    @coroutine
    def handle_channel_message(self, channel, message):
        if channel not in self.subscriptions:
            raise Return((True, None))

        response = Response(method='message', body=message)
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

        func = getattr(self.application, 'handle_%s' % method, None)
        if not func:
            raise Return((None, self.application.METHOD_NOT_FOUND))

        result, error = yield func(params)
        raise Return((result, error))

    def add_subscription(self, project_id, namespace_name, channel, client):
        """
        Subscribe application on channel if necessary and register client
        to receive messages from that channel.
        """
        subscription_key = self.get_subscription_key(project_id, namespace_name, channel)
        self.subscriber.subscribe(six.u(subscription_key), callback=self.dispatch_published_message)

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
                self.subscriber.unsubscribe(six.u(subscription_key))
                del self.subscriptions[subscription_key]
        except KeyError:
            pass
