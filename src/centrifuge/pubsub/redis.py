# coding: utf-8
#
# Copyright (c) Alexandr Emelin. MIT license.
# All rights reserved.

import six
import toredis
from tornado.ioloop import PeriodicCallback
from tornado.gen import coroutine, Return
from tornado.iostream import StreamClosedError
from tornado.escape import json_encode, json_decode

from centrifuge.log import logger
from centrifuge.response import Response
from centrifuge.pubsub.base import BasePubSub, ADMIN_CHANNEL, CONTROL_CHANNEL


class PubSub(BasePubSub):
    """
    This class manages application PUB/SUB logic.
    """
    NAME = 'Redis'

    OK_RESPONSE = b"OK"

    def __init__(self, application):
        super(PubSub, self).__init__(application)
        self.subscriber = toredis.Client()
        self.publisher = toredis.Client()
        self._need_reconnect = False
        self.host = None
        self.port = None
        self.password = None
        self.db = 0
        self.connection_check = None

    def initialize(self):
        options = self.application.settings['options']
        self.host = options.redis_host
        self.port = options.redis_port
        self.db = options.redis_db
        self.password = options.redis_password
        self.connection_check = PeriodicCallback(self.check_connection, 1000)
        self.connect()
        logger.info("Redis PUB/SUB at {0}:{1} (db {2})".format(self.host, self.port, self.db))

    def on_subscriber_auth(self, res):
        if res != self.OK_RESPONSE:
            logger.error("pubsub auth for subscriber: {0}".format(res))

    def on_publisher_auth(self, res):
        if res != self.OK_RESPONSE:
            logger.error("pubsub auth for publisher: {0}".format(res))

    def on_subscriber_select(self, res):
        """
        After selecting subscriber database subscribe on channels
        """
        if res != self.OK_RESPONSE:
            # error returned
            logger.error("pubsub select database for subscriber: {0}".format(res))
            return

        self.subscriber.subscribe(CONTROL_CHANNEL, callback=self.dispatch_redis_message)
        self.subscriber.subscribe(ADMIN_CHANNEL, callback=self.dispatch_redis_message)

        for subscription in self.subscriptions.copy():
            if subscription not in self.subscriptions:
                continue
            self.subscriber.subscribe(subscription, callback=self.dispatch_published_message)

    def on_publisher_select(self, res):
        if res != self.OK_RESPONSE:
            logger.error("pubsub select database for publisher: {0}".format(res))
            self._need_reconnect = True

    def connect(self):
        """
        Connect from scratch, resubscribe on channels etc
        """
        try:
            self.subscriber.connect(host=self.host, port=self.port)
            self.publisher.connect(host=self.host, port=self.port)
        except Exception as e:
            logger.error("error connecting to Redis server: %s" % (str(e)))
        else:
            if self.password:
                self.subscriber.auth(self.password, callback=self.on_subscriber_auth)
                self.publisher.auth(self.password, callback=self.on_publisher_auth)

            self.subscriber.select(self.db, callback=self.on_subscriber_select)
            self.publisher.select(self.db, callback=self.on_publisher_select)

        self.connection_check.stop()
        self.connection_check.start()

    def check_connection(self):
        connection_dropped = not self.subscriber.is_connected() or not self.publisher.is_connected()
        if connection_dropped or self._need_reconnect:
            logger.info('reconnecting to Redis')
            self._need_reconnect = False
            self.connect()

    def publish(self, channel, body, method=None):
        """
        Publish message into channel of stream.
        """
        if channel == CONTROL_CHANNEL or channel == ADMIN_CHANNEL:
            to_publish = json_encode(body)
        else:
            response = Response()
            method = method or self.DEFAULT_PUBLISH_METHOD
            response.method = method
            response.body = body
            to_publish = response.as_message()

        try:
            self.publisher.publish(channel, to_publish)
        except StreamClosedError as e:
            self._need_reconnect = True
            logger.error(e)

    @coroutine
    def dispatch_redis_message(self, multipart_message):
        """
        Got message, decide what is it and dispatch into right
        application handler.
        """
        msg_type = multipart_message[0]
        if six.PY3:
            msg_type = msg_type.decode()

        if msg_type != 'message':
            return

        channel = multipart_message[1]
        if six.PY3:
            channel = channel.decode()

        if channel == CONTROL_CHANNEL:
            yield self.handle_control_message(json_decode(multipart_message[2]))
        elif channel == ADMIN_CHANNEL:
            yield self.handle_admin_message(json_decode(multipart_message[2]))
        else:
            yield self.handle_message(channel, multipart_message[2])

    @coroutine
    def handle_message(self, channel, message_data):
        if channel not in self.subscriptions:
            raise Return((True, None))
        for uid, client in six.iteritems(self.subscriptions[channel]):
            if channel in self.subscriptions and uid in self.subscriptions[channel]:
                yield client.send(message_data)

    def subscribe_key(self, subscription_key):
        self.subscriber.subscribe(
            six.u(subscription_key), callback=self.dispatch_redis_message
        )

    def unsubscribe_key(self, subscription_key):
        self.subscriber.unsubscribe(six.u(subscription_key))
