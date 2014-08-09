# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import time
import six
import heapq

from tornado.gen import coroutine, Return
from tornado.ioloop import PeriodicCallback

from centrifuge.utils import json_encode
from centrifuge.response import Response
from centrifuge.log import logger
from centrifuge.engine import BaseEngine


class Engine(BaseEngine):

    NAME = 'In memory - single node only'

    HISTORY_EXPIRE_TASK_INTERVAL = 60000  # once in a minute

    def __init__(self, *args, **kwargs):
        super(Engine, self).__init__(*args, **kwargs)
        self.subscriptions = {}
        self.history = {}
        self.history_expire_at = {}
        self.history_expire_heap = []
        self.presence = {}
        self.deactivated = {}
        self.history_expire_task = PeriodicCallback(
            self.check_history_expire,
            self.HISTORY_EXPIRE_TASK_INTERVAL
        )

    def initialize(self):
        self.history_expire_task.start()
        logger.info("Memory engine initialized")

    @coroutine
    def publish_message(self, channel, body, method=BaseEngine.DEFAULT_PUBLISH_METHOD):
        yield self.handle_message(channel, method, body)
        raise Return((True, None))

    @coroutine
    def publish_control_message(self, message):
        yield self.handle_control_message(message)
        raise Return((True, None))

    @coroutine
    def publish_admin_message(self, message):
        yield self.handle_admin_message(message)
        raise Return((True, None))

    @coroutine
    def handle_admin_message(self, message):
        message = json_encode(message)
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
    def handle_message(self, channel, method, body):

        if channel not in self.subscriptions:
            raise Return((True, None))

        timer = None
        if self.application.collector:
            timer = self.application.collector.get_timer('broadcast')

        response = Response(method=method, body=body)
        prepared_response = response.as_message()
        for uid, client in six.iteritems(self.subscriptions[channel]):
            if channel in self.subscriptions and uid in self.subscriptions[channel]:
                yield client.send(prepared_response)

        if timer:
            timer.stop()

        raise Return((True, None))

    @coroutine
    def add_subscription(self, project_id, channel, client):
        """
        Subscribe application on channel if necessary and register client
        to receive messages from that channel.
        """
        subscription_key = self.get_subscription_key(project_id, channel)

        if subscription_key not in self.subscriptions:
            self.subscriptions[subscription_key] = {}

        self.subscriptions[subscription_key][client.uid] = client

        raise Return((True, None))

    @coroutine
    def remove_subscription(self, project_id, channel, client):
        """
        Unsubscribe application from channel if necessary and prevent client
        from receiving messages from that channel.
        """
        subscription_key = self.get_subscription_key(project_id, channel)

        try:
            del self.subscriptions[subscription_key][client.uid]
        except KeyError:
            pass

        try:
            if not self.subscriptions[subscription_key]:
                del self.subscriptions[subscription_key]
        except KeyError:
            pass

        raise Return((True, None))

    def get_presence_key(self, project_id, channel):
        return "%s:presence:%s:%s" % (self.prefix, project_id, channel)

    @coroutine
    def add_presence(self, project_id, channel, uid, user_info, presence_timeout=None):
        now = int(time.time())
        expire_at = now + (presence_timeout or self.presence_timeout)

        hash_key = self.get_presence_key(project_id, channel)

        if hash_key not in self.presence:
            self.presence[hash_key] = {}

        self.presence[hash_key][uid] = {
            'expire_at': expire_at,
            'user_info': user_info
        }

        raise Return((True, None))

    @coroutine
    def remove_presence(self, project_id, channel, uid):
        hash_key = self.get_presence_key(project_id, channel)
        try:
            del self.presence[hash_key][uid]
        except KeyError:
            pass

        raise Return((True, None))

    @coroutine
    def get_presence(self, project_id, channel):
        now = int(time.time())
        hash_key = self.get_presence_key(project_id, channel)
        to_return = {}
        if hash_key in self.presence:
            keys_to_delete = []
            for uid, data in six.iteritems(self.presence[hash_key]):
                expire_at = data['expire_at']
                if expire_at > now:
                    to_return[uid] = data['user_info']
                else:
                    keys_to_delete.append(uid)

            for uid in keys_to_delete:
                try:
                    del self.presence[hash_key][uid]
                except KeyError:
                    pass

            if not self.presence[hash_key]:
                try:
                    del self.presence[hash_key]
                except KeyError:
                    pass

        raise Return((to_return, None))

    def get_history_key(self, project_id, channel):
        return "%s:history:%s:%s" % (self.prefix, project_id, channel)

    @coroutine
    def add_history_message(self, project_id, channel, message, history_size=None, history_expire=0):

        history_key = self.get_history_key(project_id, channel)

        if history_expire:
            expire_at = int(time.time()) + history_expire
            self.history_expire_at[history_key] = expire_at
            heapq.heappush(self.history_expire_heap, (expire_at, history_key))
        elif history_key in self.history_expire_at:
            del self.history_expire_at[history_key]

        if history_key not in self.history:
            self.history[history_key] = []

        history_size = history_size or self.history_size

        self.history[history_key].insert(0, message)
        self.history[history_key] = self.history[history_key][:history_size]

        raise Return((True, None))

    @coroutine
    def get_history(self, project_id, channel):
        history_key = self.get_history_key(project_id, channel)

        now = int(time.time())

        if history_key in self.history_expire_at:
            expire_at = self.history_expire_at[history_key]
            if expire_at <= now:
                self.remove_history(history_key)
                raise Return(([], None))

        try:
            data = self.history[history_key]
        except KeyError:
            data = []

        raise Return((data, None))

    def remove_history(self, history_key):
        try:
            del self.history[history_key]
        except KeyError:
            pass
        try:
            del self.history_expire_at[history_key]
        except KeyError:
            pass

    def check_history_expire(self):
        now = int(time.time())
        while self.history_expire_heap:
            if self.history_expire_heap[0][0] <= now:
                expire, history_key = heapq.heappop(self.history_expire_heap)
                if history_key in self.history_expire_at and self.history_expire_at[history_key] <= now:
                    self.remove_history(history_key)
            else:
                break
