# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import time
import six

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

from tornado.ioloop import PeriodicCallback
from tornado.gen import coroutine, Return, Task
from tornado.iostream import StreamClosedError

import toredis

from centrifuge.utils import json_encode, json_decode
from centrifuge.response import Response
from centrifuge.log import logger
from centrifuge.engine import BaseEngine

from tornado.options import define

define(
    "redis_host", default="localhost", help="Redis host", type=str
)

define(
    "redis_port", default=6379, help="Redis port", type=int
)

define(
    "redis_db", default=0, help="Redis database number", type=int
)

define(
    "redis_password", default="", help="Redis auth password", type=str
)

define(
    "redis_url", default="", help="Redis URL", type=str
)

define(
    "redis_api", default=False, help="enable Redis API listener", type=bool
)


range_func = six.moves.xrange


def prepare_key_value(pair):
    if not pair:
        return
    key = pair[0].decode()
    try:
        value = json_decode(pair[1].decode())
    except ValueError:
        value = {}
    return key, value


def dict_from_list(key_value_list):
    # noinspection PyTypeChecker
    return dict(
        prepare_key_value(key_value_list[i:i+2]) for i in range_func(0, len(key_value_list), 2)
    )


class Engine(BaseEngine):
    """
    This is Redis engine. It allows to start many instances of Centrifuge and they will
    be connected between each other due to Redis PUB/SUB mechanism. Of course you need
    Redis server running to use this engine.
    """

    NAME = 'Redis'

    OK_RESPONSE = b'OK'

    def __init__(self, *args, **kwargs):
        super(Engine, self).__init__(*args, **kwargs)

        self.api_key = "{0}.{1}".format(self.prefix, "api")

        if not self.options.redis_url:
            self.host = self.options.redis_host
            self.port = self.options.redis_port
            self.password = self.options.redis_password
            self.db = self.options.redis_db
        else:
            # according to https://devcenter.heroku.com/articles/redistogo
            parsed_url = urlparse.urlparse(self.options.redis_url)
            self.host = parsed_url.hostname
            self.port = int(parsed_url.port)
            self.db = 0
            self.password = parsed_url.password

        self.connection_check = PeriodicCallback(self.check_connection, 1000)
        self._need_reconnect = False

        self.subscriber = toredis.Client(io_loop=self.io_loop)
        self.publisher = toredis.Client(io_loop=self.io_loop)
        self.worker = toredis.Client(io_loop=self.io_loop)
        if self.options.redis_api:
            self.listener = toredis.Client(io_loop=self.io_loop)

        self.subscriptions = {}

    def initialize(self):
        self.connect()
        logger.info("Redis engine at {0}:{1} (db {2})".format(self.host, self.port, self.db))
        if self.options.redis_api:
            logger.info(
                "Redis API endpoint enabled via RPUSH to {0} key".format(self.api_key)
            )

    def on_auth(self, res):
        if res != self.OK_RESPONSE:
            logger.error("auth failed: {0}".format(res))

    def on_subscriber_select(self, res):
        """
        After selecting subscriber database subscribe on channels
        """
        if res != self.OK_RESPONSE:
            # error returned
            logger.error("select database failed: {0}".format(res))
            self._need_reconnect = True
            return

        self.subscriber.subscribe(self.admin_channel_name, callback=self.on_redis_message)
        self.subscriber.subscribe(self.control_channel_name, callback=self.on_redis_message)

        for subscription in self.subscriptions.copy():
            if subscription not in self.subscriptions:
                continue
            self.subscriber.subscribe(subscription, callback=self.on_redis_message)

    @coroutine
    def process_api_messages(self):
        while True:
            message = yield Task(self.listener.blpop, self.api_key, 0)
            if message:
                yield self.on_api_message(message)

    def on_listener_select(self, res):
        if res != self.OK_RESPONSE:
            # error returned
            logger.error("select database failed: {0}".format(res))
            self._need_reconnect = True
            return

        self.process_api_messages()

    def on_select(self, res):
        if res != self.OK_RESPONSE:
            logger.error("select database failed: {0}".format(res))
            self._need_reconnect = True

    def connect(self):
        """
        Connect from scratch if connection not established.
        """
        subscriber_connect = False
        publisher_connect = False
        worker_connect = False
        listener_connect = False
        try:
            if not self.subscriber.is_connected():
                subscriber_connect = True
                self.subscriber.connect(host=self.host, port=self.port)
            if not self.publisher.is_connected():
                publisher_connect = True
                self.publisher.connect(host=self.host, port=self.port)
            if not self.worker.is_connected():
                worker_connect = True
                self.worker.connect(host=self.host, port=self.port)
            if self.options.redis_api:
                if not self.listener.is_connected():
                    listener_connect = True
                    self.listener.connect(host=self.host, port=self.port)
        except Exception as e:
            logger.error("error connecting to Redis server: %s" % (str(e)))
        else:
            if self.password:
                if subscriber_connect:
                    self.subscriber.auth(self.password, callback=self.on_auth)
                if publisher_connect:
                    self.publisher.auth(self.password, callback=self.on_auth)
                if worker_connect:
                    self.worker.auth(self.password, callback=self.on_auth)
                if self.options.redis_api:
                    if listener_connect:
                        self.listener.auth(self.password, callback=self.on_auth)

            if subscriber_connect:
                self.subscriber.select(self.db, callback=self.on_subscriber_select)
            if publisher_connect:
                self.publisher.select(self.db, callback=self.on_select)
            if worker_connect:
                self.worker.select(self.db, callback=self.on_select)
            if self.options.redis_api:
                if listener_connect:
                    self.listener.select(self.db, callback=self.on_listener_select)

        self.connection_check.stop()
        self.connection_check.start()

    def check_connection(self):
        conn_statuses = [
            self.subscriber.is_connected(),
            self.publisher.is_connected(),
            self.worker.is_connected()
        ]
        if self.options.redis_api:
            conn_statuses.append(self.listener.is_connected())

        connection_dropped = not all(conn_statuses)
        if connection_dropped or self._need_reconnect:
            logger.info('reconnecting to Redis')
            self._need_reconnect = False
            self.connect()

    def _publish(self, channel, message):
        try:
            self.publisher.publish(channel, message)
        except StreamClosedError as e:
            self._need_reconnect = True
            logger.error(e)
            return False
        else:
            return True

    @coroutine
    def publish_message(self, channel, body, method="message"):
        """
        Publish message into channel of stream.
        """
        response = Response()
        response.method = method
        response.body = body
        to_publish = response.as_message()
        result = self._publish(channel, to_publish)
        raise Return((result, None))

    @coroutine
    def publish_control_message(self, message):
        result = self._publish(self.control_channel_name, json_encode(message))
        raise Return((result, None))

    @coroutine
    def publish_admin_message(self, message):
        result = self._publish(self.admin_channel_name, json_encode(message))
        raise Return((result, None))

    @coroutine
    def on_api_message(self, redis_message):
        """
        Got message from Redis, dispatch it into right message handler.
        """
        try:
            message = json_decode(redis_message[1])
        except ValueError:
            logger.error("Redis API - malformed JSON")
            return

        if not isinstance(message, dict):
            logger.error("Redis API - object expected")
            return

        project_key = message.get("project")
        if not project_key:
            logger.error("Redis API - project required")
            return

        data = message.get("data")
        if not data:
            logger.error("Redis API - data required")

        project = self.application.get_project(project_key)
        if not project:
            logger.error("Redis API - project not found")
            return

        _, error = yield self.application.process_api_data(project, data, False)
        if error:
            logger.error(error)

    @coroutine
    def on_redis_message(self, redis_message):
        """
        Got message from Redis, dispatch it into right message handler.
        """
        if not redis_message:
            return

        msg_type = redis_message[0]
        if six.PY3:
            msg_type = msg_type.decode()

        if msg_type != 'message':
            return

        channel = redis_message[1]
        if six.PY3:
            channel = channel.decode()

        if channel == self.control_channel_name:
            yield self.handle_control_message(json_decode(redis_message[2]))
        elif channel == self.admin_channel_name:
            yield self.handle_admin_message(redis_message[2])
        else:
            yield self.handle_message(channel, redis_message[2])

    @coroutine
    def handle_admin_message(self, message):
        for uid, connection in six.iteritems(self.application.admin_connections):
            if uid not in self.application.admin_connections:
                continue
            connection.send(message)

        raise Return((True, None))

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

    @coroutine
    def handle_message(self, channel, message_data):
        if channel not in self.subscriptions:
            raise Return((True, None))

        timer = None
        if self.application.collector:
            timer = self.application.collector.get_timer('broadcast')

        for uid, client in six.iteritems(self.subscriptions[channel]):
            if channel in self.subscriptions and uid in self.subscriptions[channel]:
                yield client.send(message_data)

        if timer:
            timer.stop()

    def subscribe_key(self, subscription_key):
        self.subscriber.subscribe(
            subscription_key, callback=self.on_redis_message
        )

    def unsubscribe_key(self, subscription_key):
        self.subscriber.unsubscribe(subscription_key)

    @coroutine
    def add_subscription(self, project_key, channel, client):

        subscription_key = self.get_subscription_key(project_key, channel)
        self.subscribe_key(subscription_key)

        if subscription_key not in self.subscriptions:
            self.subscriptions[subscription_key] = {}

        self.subscriptions[subscription_key][client.uid] = client

        raise Return((True, None))

    @coroutine
    def remove_subscription(self, project_key, channel, client):

        subscription_key = self.get_subscription_key(project_key, channel)

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

        raise Return((True, None))

    def get_presence_hash_key(self, project_key, channel):
        return "%s.presence.hash.%s.%s" % (self.prefix, project_key, channel)

    def get_presence_set_key(self, project_key, channel):
        return "%s.presence.set.%s.%s" % (self.prefix, project_key, channel)

    def get_history_list_key(self, project_key, channel):
        return "%s.history.list.%s.%s" % (self.prefix, project_key, channel)

    @coroutine
    def add_presence(self, project_key, channel, uid, user_info, presence_timeout=None):
        now = int(time.time())
        expire_at = now + (presence_timeout or self.presence_timeout)
        hash_key = self.get_presence_hash_key(project_key, channel)
        set_key = self.get_presence_set_key(project_key, channel)
        try:
            pipeline = self.worker.pipeline()
            pipeline.multi()
            pipeline.zadd(set_key, {uid: expire_at})
            pipeline.hset(hash_key, uid, json_encode(user_info))
            pipeline.execute()
            yield Task(pipeline.send)
        except StreamClosedError as e:
            raise Return((None, e))
        else:
            raise Return((True, None))

    @coroutine
    def remove_presence(self, project_key, channel, uid):
        hash_key = self.get_presence_hash_key(project_key, channel)
        set_key = self.get_presence_set_key(project_key, channel)
        try:
            pipeline = self.worker.pipeline()
            pipeline.hdel(hash_key, uid)
            pipeline.zrem(set_key, uid)
            yield Task(pipeline.send)
        except StreamClosedError as e:
            raise Return((None, e))
        else:
            raise Return((True, None))

    @coroutine
    def get_presence(self, project_key, channel):
        now = int(time.time())
        hash_key = self.get_presence_hash_key(project_key, channel)
        set_key = self.get_presence_set_key(project_key, channel)
        try:
            expired_keys = yield Task(self.worker.zrangebyscore, set_key, 0, now)
            if expired_keys:
                pipeline = self.worker.pipeline()
                pipeline.zremrangebyscore(set_key, 0, now)
                pipeline.hdel(hash_key, [x.decode() for x in expired_keys])
                yield Task(pipeline.send)
            data = yield Task(self.worker.hgetall, hash_key)
        except StreamClosedError as e:
            raise Return((None, e))
        else:
            raise Return((dict_from_list(data), None))

    @coroutine
    def add_history_message(self, project_key, channel, message, history_size, history_lifetime):
        history_list_key = self.get_history_list_key(project_key, channel)
        try:
            pipeline = self.worker.pipeline()
            pipeline.lpush(history_list_key, json_encode(message))
            pipeline.ltrim(history_list_key, 0, history_size - 1)
            if history_lifetime:
                pipeline.expire(history_list_key, history_lifetime)
            else:
                pipeline.persist(history_list_key)
            yield Task(pipeline.send)
        except StreamClosedError as e:
            raise Return((None, e))
        else:
            raise Return((True, None))

    @coroutine
    def get_history(self, project_key, channel):
        history_list_key = self.get_history_list_key(project_key, channel)
        try:
            data = yield Task(self.worker.lrange, history_list_key, 0, -1)
        except StreamClosedError as e:
            raise Return((None, e))
        else:
            raise Return(([json_decode(x.decode()) for x in data], None))
