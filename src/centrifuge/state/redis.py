# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import toredis
import time
from tornado.ioloop import PeriodicCallback
from tornado.gen import coroutine, Return, Task
from tornado.escape import json_decode, json_encode
from tornado.iostream import StreamClosedError
from six import PY3

from centrifuge.log import logger
from centrifuge.state.base import State as BaseState


if PY3:
    range_func = range
else:
    range_func = xrange


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


class State(BaseState):

    NAME = "Redis"

    OK_RESPONSE = "OK"

    def __init__(self, *args, **kwargs):
        super(State, self).__init__(*args, **kwargs)
        self.host = None
        self.port = None
        self.db = None
        self.client = None
        self.connection_check = None

    def initialize(self):
        settings = self.config.get('settings', {})
        self.host = settings.get("host", "localhost")
        self.port = settings.get("port", 6379)
        self.db = settings.get("db", 0)
        self.client = toredis.Client(io_loop=self.io_loop)
        self.client.state = self
        self.connection_check = PeriodicCallback(self.check_connection, 1000)
        self.connect()
        logger.info("Redis State initialized")

    def on_select(self, res):
        if res != self.OK_RESPONSE:
            logger.error("state select database: {0}".format(res))

    def connect(self):
        """
        Connect to Redis.
        Do not even try to connect if State is faked.
        """
        if self.fake:
            return

        try:
            self.client.connect(host=self.host, port=self.port)
        except Exception as e:
            logger.error("error connecting to Redis server: %s" % (str(e)))
        else:
            if self.db and isinstance(self.db, int):
                self.client.select(self.db, callback=self.on_select)

        self.connection_check.stop()
        self.connection_check.start()

    def check_connection(self):
        if not self.client.is_connected():
            logger.info('reconnecting to Redis')
            self.connect()

    @staticmethod
    def get_presence_set_key(project_id, namespace, channel):
        return "centrifuge:presence:set:%s:%s:%s" % (project_id, namespace, channel)

    @coroutine
    def add_presence(self, project_id, namespace, channel, uid, user_info, presence_timeout=None):
        """
        Add user's presence with appropriate expiration time.
        Must be called when user subscribes on channel.
        """
        if self.fake:
            raise Return((True, None))
        now = int(time.time())
        expire_at = now + (presence_timeout or self.presence_timeout)
        hash_key = self.get_presence_hash_key(project_id, namespace, channel)
        set_key = self.get_presence_set_key(project_id, namespace, channel)
        try:
            yield Task(self.client.zadd, set_key, {uid: expire_at})
            yield Task(self.client.hset, hash_key, uid, json_encode(user_info))
        except StreamClosedError as e:
            raise Return((None, e))
        else:
            raise Return((True, None))

    @coroutine
    def remove_presence(self, project_id, namespace, channel, uid):
        """
        Remove user's presence from Redis.
        Must be called on disconnects of any kind.
        """
        if self.fake:
            raise Return((True, None))
        hash_key = self.get_presence_hash_key(project_id, namespace, channel)
        set_key = self.get_presence_set_key(project_id, namespace, channel)
        try:
            yield Task(self.client.hdel, hash_key, uid)
            yield Task(self.client.zrem, set_key, uid)
        except StreamClosedError as e:
            raise Return((None, e))
        else:
            raise Return((True, None))

    @coroutine
    def get_presence(self, project_id, namespace, channel):
        """
        Get presence for channel.
        """
        if self.fake:
            raise Return((None, None))
        now = int(time.time())
        hash_key = self.get_presence_hash_key(project_id, namespace, channel)
        set_key = self.get_presence_set_key(project_id, namespace, channel)
        try:
            expired_keys = yield Task(self.client.zrangebyscore, set_key, 0, now)
            if expired_keys:
                yield Task(self.client.zremrangebyscore, set_key, 0, now)
                yield Task(self.client.hdel, hash_key, [x.decode() for x in expired_keys])
            data = yield Task(self.client.hgetall, hash_key)
        except StreamClosedError:
            raise Return((None, 'presence unavailable'))
        else:
            raise Return((dict_from_list(data), None))

    @coroutine
    def add_history_message(self, project_id, namespace, channel, message, history_size=None):
        """
        Add message to channel's history.
        Must be called when new message has been published.
        """
        if self.fake:
            raise Return((True, None))
        history_size = history_size or self.history_size
        list_key = self.get_history_list_key(project_id, namespace, channel)
        try:
            yield Task(self.client.lpush, list_key, json_encode(message))
            yield Task(self.client.ltrim, list_key, 0, history_size - 1)
        except StreamClosedError as e:
            raise Return((None, e))
        else:
            raise Return((True, None))

    @coroutine
    def get_history(self, project_id, namespace, channel):
        """
        Get a list of last messages for channel.
        """
        if self.fake:
            raise Return((None, None))
        history_list_key = self.get_history_list_key(project_id, namespace, channel)
        try:
            data = yield Task(self.client.lrange, history_list_key, 0, -1)
        except StreamClosedError:
            raise Return((None, self.application.INTERNAL_SERVER_ERROR))
        else:
            raise Return(([json_decode(x.decode()) for x in data], None))
