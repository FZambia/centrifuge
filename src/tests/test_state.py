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
        self.uid_1 = 'test-1'
        self.uid_2 = 'test-2'
        self.user_id = 'test'
        self.user_id_extra = 'test_extra'
        self.user_info = 'test user info'
        self.message_1 = 'test message 1'
        self.message_2 = 'test message 2'
        self.message_3 = 'test message 3'
        self.state = State(io_loop=self.io_loop, history_size=2, presence_timeout=1)
        self.state.connect()

    @gen_test
    def test_presence(self):
        result = yield Task(self.state.client.flushdb)
        self.assertEqual(result, "OK")

        result, error = yield self.state.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(result, {})

        result, error = yield self.state.add_presence(
            self.project_id, self.category, self.channel,
            self.uid_1, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.state.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertTrue(self.uid_1 in result)

        result, error = yield self.state.add_presence(
            self.project_id, self.category, self.channel,
            self.uid_1, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.state.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertEqual(len(result), 1)

        result, error = yield self.state.add_presence(
            self.project_id, self.category, self.channel,
            self.uid_2, self.user_info
        )
        self.assertEqual(result, True)

        result, error = yield self.state.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertTrue(self.uid_2 in result)
        self.assertEqual(len(result), 2)

        result, error = yield self.state.remove_presence(
            self.project_id, self.category, self.channel, self.uid_2
        )
        self.assertEqual(result, True)

        result, error = yield self.state.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertTrue(self.uid_1 in result)
        self.assertTrue(self.uid_2 not in result)
        self.assertEqual(len(result), 1)

        time.sleep(2)
        result, error = yield self.state.get_presence(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(result, {})

    @gen_test
    def test_history(self):
        result = yield Task(self.state.client.flushdb)
        self.assertEqual(result, "OK")

        result, error = yield self.state.add_history_message(
            self.project_id, self.category, self.channel, self.message_1
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.state.get_history(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 1)

        result, error = yield self.state.add_history_message(
            self.project_id, self.category, self.channel, self.message_2
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.state.get_history(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 2)

        result, error = yield self.state.add_history_message(
            self.project_id, self.category, self.channel, self.message_3
        )
        self.assertEqual(error, None)
        self.assertEqual(result, True)

        result, error = yield self.state.get_history(
            self.project_id, self.category, self.channel
        )
        self.assertEqual(error, None)
        self.assertEqual(len(result), 2)
        self.assertEqual(result, [self.message_3, self.message_2])


if __name__ == '__main__':
    main()