# coding: utf-8
from __future__ import print_function
from tornado.gen import Task
from tornado.testing import AsyncTestCase, gen_test, main
import time
from centrifuge.state import State


class StateTest(AsyncTestCase):
    """ Test the client """

    def setUp(self):
        super(StateTest, self).setUp()
        self.project_id = 'test'
        self.category = 'test'
        self.channel = 'test'
        self.user_id = 'test'
        self.user_id_extra = 'test_extra'
        self.message_1 = 'test message 1'
        self.message_2 = 'test message 2'
        self.message_3 = 'test message 3'
        self.store = State(io_loop=self.io_loop, history_size=2, presence_timeout=1)

    @gen_test
    def test_presence(self):
        result = yield Task(self.store.client.flushdb)
        self.assertEqual(result, "OK")

        result, error = yield self.store.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(result, {})

        result, error = yield self.store.add_presence(
            self.project_id, self.category, self.channel, self.user_id
        )
        self.assertEqual(result, True)

        result, error = yield self.store.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertTrue(self.user_id in result)

        result, error = yield self.store.add_presence(
            self.project_id, self.category, self.channel, self.user_id
        )
        self.assertEqual(result, True)

        result, error = yield self.store.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertTrue(self.user_id in result)
        self.assertEqual(len(result), 1)

        result, error = yield self.store.add_presence(
            self.project_id, self.category, self.channel, self.user_id_extra
        )
        self.assertEqual(result, True)

        result, error = yield self.store.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertTrue(self.user_id in result)
        self.assertTrue(self.user_id_extra in result)
        self.assertEqual(len(result), 2)

        result, error = yield self.store.remove_presence(
            self.project_id, self.category, self.channel, self.user_id_extra
        )
        self.assertEqual(result, True)

        result, error = yield self.store.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertTrue(self.user_id in result)
        self.assertTrue(self.user_id_extra not in result)
        self.assertEqual(len(result), 1)

        time.sleep(2)
        result, error = yield self.store.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(result, {})

    @gen_test
    def test_history(self):
        result = yield Task(self.store.client.flushdb)
        self.assertEqual(result, "OK")

        result, error = yield self.store.add_history_message(
            self.project_id, self.category, self.channel, self.message_1
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.store.get_history(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 1)

        result, error = yield self.store.add_history_message(
            self.project_id, self.category, self.channel, self.message_2
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.store.get_history(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 2)

        result, error = yield self.store.add_history_message(
            self.project_id, self.category, self.channel, self.message_3
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.store.get_history(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, [self.message_3, self.message_2])


if __name__ == '__main__':
    main()