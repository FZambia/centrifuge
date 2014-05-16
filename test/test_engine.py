# coding: utf-8
from unittest import main
import sys
import os
import json
import time
from tornado.gen import Task
from tornado.testing import AsyncTestCase, gen_test


from centrifuge.engine import BaseEngine
from centrifuge.engine.memory import Engine as MemoryEngine
from centrifuge.engine.redis import Engine as RedisEngine
from centrifuge.core import Application


class FakeClient(object):

    uid = 'test_uid'


class Options(object):

    redis_host = "localhost"
    redis_port = 6379
    redis_password = ""
    redis_db = 0
    redis_url = ""


class BaseEngineTest(AsyncTestCase):

    def setUp(self):
        super(BaseEngineTest, self).setUp()
        self.application = Application(**{'options': Options})
        self.engine = BaseEngine(self.application)

    def test_get_subscription_key(self):
        key = self.engine.get_subscription_key('project', 'channel')
        self.assertEqual(key, "centrifuge|project|channel")


class MemoryEngineTest(AsyncTestCase):

    def setUp(self):
        super(MemoryEngineTest, self).setUp()
        self.application = Application(**{'options': Options})
        self.engine = MemoryEngine(self.application)
        self.engine.initialize()
        self.engine.history_size = 2
        self.engine.presence_timeout = 1
        self.project_id = "project_id"
        self.channel = "channel"
        self.uid_1 = 'uid-1'
        self.uid_2 = 'uid-2'
        self.user_id = 'user_id'
        self.user_id_extra = 'user_id_extra'
        self.user_info = "{}"
        self.message_1 = json.dumps('test message 1')
        self.message_2 = json.dumps('test message 2')
        self.message_3 = json.dumps('test message 3')

    @gen_test
    def test_add_subscription(self):
        yield self.engine.add_subscription(self.project_id, self.channel, FakeClient())

        self.assertTrue(
            self.engine.get_subscription_key(
                self.project_id, self.channel
            ) in self.engine.subscriptions
        )

    @gen_test
    def test_remove_subscription(self):
        yield self.engine.remove_subscription(self.project_id, self.channel, FakeClient())

        self.assertTrue(
            self.engine.get_subscription_key(
                self.project_id, self.channel
            ) not in self.engine.subscriptions
        )

    @gen_test
    def test_presence(self):
        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertEqual(result, {})

        result, error = yield self.engine.add_presence(
            self.project_id, self.channel, self.uid_1, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertTrue(self.uid_1 in result)

        result, error = yield self.engine.add_presence(
            self.project_id, self.channel,
            self.uid_1, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertEqual(len(result), 1)

        result, error = yield self.engine.add_presence(
            self.project_id, self.channel,
            self.uid_2, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertTrue(self.uid_2 in result)
        self.assertEqual(len(result), 2)

        result, error = yield self.engine.remove_presence(
            self.project_id, self.channel, self.uid_2
        )
        self.assertEqual(result, True)

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertTrue(self.uid_2 not in result)
        self.assertEqual(len(result), 1)

        time.sleep(2)
        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertEqual(result, {})

    @gen_test
    def test_history(self):
        result, error = yield self.engine.add_history_message(
            self.project_id, self.channel, self.message_1
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 1)

        result, error = yield self.engine.add_history_message(
            self.project_id, self.channel, self.message_2
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 2)

        result, error = yield self.engine.add_history_message(
            self.project_id, self.channel, self.message_3
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 2)

    @gen_test
    def test_history_expire(self):
        result, error = yield self.engine.add_history_message(
            self.project_id, self.channel, self.message_1, history_expire=1
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 1)

        time.sleep(2)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 0)


class RedisEngineTest(AsyncTestCase):
    """ Test the client """

    def setUp(self):
        super(RedisEngineTest, self).setUp()
        self.application = Application(**{'options': Options})
        self.engine = RedisEngine(self.application, io_loop=self.io_loop)
        self.engine.initialize()
        self.engine.history_size = 2
        self.engine.presence_timeout = 1
        self.project_id = "project_id"
        self.channel = "channel"
        self.uid_1 = 'uid-1'
        self.uid_2 = 'uid-2'
        self.user_id = 'user_id'
        self.user_id_extra = 'user_id_extra'
        self.user_info = "{}"
        self.message_1 = json.dumps('test message 1')
        self.message_2 = json.dumps('test message 2')
        self.message_3 = json.dumps('test message 3')

    @gen_test
    def test_presence(self):

        result = yield Task(self.engine.worker.flushdb)
        self.assertEqual(result, b"OK")

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertEqual(result, {})

        result, error = yield self.engine.add_presence(
            self.project_id, self.channel,
            self.uid_1, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertTrue(self.uid_1 in result)

        result, error = yield self.engine.add_presence(
            self.project_id, self.channel,
            self.uid_1, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertEqual(len(result), 1)

        result, error = yield self.engine.add_presence(
            self.project_id, self.channel,
            self.uid_2, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertTrue(self.uid_2 in result)
        self.assertEqual(len(result), 2)

        result, error = yield self.engine.remove_presence(
            self.project_id, self.channel, self.uid_2
        )
        self.assertEqual(result, True)

        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertTrue(self.uid_2 not in result)
        self.assertEqual(len(result), 1)

        time.sleep(2)
        result, error = yield self.engine.get_presence(
            self.project_id, self.channel
        )
        self.assertEqual(result, {})

    @gen_test
    def test_history(self):
        result = yield Task(self.engine.worker.flushdb)
        self.assertEqual(result, b"OK")

        result, error = yield self.engine.add_history_message(
            self.project_id, self.channel, self.message_1
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 1)

        result, error = yield self.engine.add_history_message(
            self.project_id, self.channel, self.message_2
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 2)

        result, error = yield self.engine.add_history_message(
            self.project_id, self.channel, self.message_3
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 2)

    @gen_test
    def test_history_expire(self):
        result = yield Task(self.engine.worker.flushdb)
        self.assertEqual(result, b"OK")

        result, error = yield self.engine.add_history_message(
            self.project_id, self.channel, self.message_1, history_expire=1
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 1)

        time.sleep(2)

        result, error = yield self.engine.get_history(
            self.project_id, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 0)


if __name__ == '__main__':
    main()
