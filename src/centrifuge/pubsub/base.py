# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import six
from tornado.gen import coroutine, Return
from tornado.escape import json_encode

from centrifuge.response import Response
from centrifuge.log import logger


# separate important parts of channel name by this
CHANNEL_NAME_SEPARATOR = ':'


# add sequence of symbols to the end of each channel name to
# prevent name overlapping
CHANNEL_SUFFIX = '>>>'


# channel for administrative interface - watch for messages travelling around.
ADMIN_CHANNEL = '_admin' + CHANNEL_SUFFIX


# channel for sharing commands among all nodes.
CONTROL_CHANNEL = '_control' + CHANNEL_SUFFIX


class BasePubSub(object):
    """
    This class manages application PUB/SUB logic.
    """
    DEFAULT_PUBLISH_METHOD = 'message'

    NAME = 'Base - single node only'

    def __init__(self, application):
        self.application = application
        self.subscriptions = {}

    def initialize(self):
        logger.info("Base PUB/SUB")

    def publish(self, channel, message, method=None):
        """
        Publish message into channel of stream.
        """
        method = method or self.DEFAULT_PUBLISH_METHOD
        message["message_type"] = method
        message["_channel"] = channel
        self.dispatch_published_message(message)

    def publish_control_message(self, message):
        self.publish(CONTROL_CHANNEL, message)

    def publish_admin_message(self, message):
        self.publish(ADMIN_CHANNEL, message)

    @staticmethod
    def get_subscription_key(project_id, namespace, channel):
        """
        Create subscription name to catch messages from specific
        project, namespace and channel.
        """
        return str(CHANNEL_NAME_SEPARATOR.join([
            'centrifuge',
            project_id,
            namespace,
            channel,
            CHANNEL_SUFFIX
        ]))

    @coroutine
    def dispatch_published_message(self, message):
        """
        Got message, decide what is it and dispatch into right
        application handler.
        """
        channel = message.pop("_channel")

        if channel == CONTROL_CHANNEL:
            yield self.handle_control_message(message)
        elif channel == ADMIN_CHANNEL:
            yield self.handle_admin_message(message)
        else:
            yield self.handle_channel_message(channel, message)

    @coroutine
    def handle_admin_message(self, message):
        message = json_encode(message)
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
                yield client.send(prepared_response)

    @coroutine
    def handle_control_message(self, message):
        """
        Handle control message.
        """
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

        self.subscribe_key(subscription_key)

        if subscription_key not in self.subscriptions:
            self.subscriptions[subscription_key] = {}

        self.subscriptions[subscription_key][client.uid] = client

        return subscription_key

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
                self.unsubscribe_key(subscription_key)
                del self.subscriptions[subscription_key]
        except KeyError:
            pass

        return subscription_key

    def subscribe_key(self, subscription_key):
        pass

    def unsubscribe_key(self, subscription_key):
        pass

    def clean(self):
        pass