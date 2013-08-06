# coding: utf-8
from __future__ import print_function
from tornado.gen import engine, Task
from tornado.testing import AsyncTestCase, gen_test, main
import time
from centrifuge.store import Store


class StoreTest(AsyncTestCase):
    """ Test the client """

    def setUp(self):
        super(StoreTest, self).setUp()
        self.project_id = 'test'
        self.category = 'test'
        self.channel = 'test'
        self.user_id = 'test'
        self.user_id_extra = 'test_extra'
        self.store = Store(io_loop=self.io_loop, history_size=3, presence_timeout=1)

    @gen_test
    def test_presence(self):
        result = yield Task(self.store.client.flushdb)
        self.assertEqual(result, "OK")
        result, error = yield self.store.get_presence(self.project_id, self.category, self.channel)
        self.assertEqual(result, [])
        result, error = yield self.store.add_presence(self.project_id, self.category, self.channel, self.user_id)
        self.assertEqual(result, True)
        result, error = yield self.store.get_presence(self.project_id, self.category, self.channel)
        self.assertEqual(result, [self.user_id, ''])
        result, error = yield self.store.add_presence(self.project_id, self.category, self.channel, self.user_id)
        self.assertEqual(result, True)
        result, error = yield self.store.get_presence(self.project_id, self.category, self.channel)
        self.assertEqual(result, [self.user_id, ''])
        result, error = yield self.store.add_presence(self.project_id, self.category, self.channel, self.user_id_extra)
        self.assertEqual(result, True)
        result, error = yield self.store.get_presence(self.project_id, self.category, self.channel)
        self.assertEqual(len(result), 4)
        result, error = yield self.store.remove_presence(self.project_id, self.category, self.channel, self.user_id_extra)
        self.assertEqual(result, True)
        result, error = yield self.store.get_presence(self.project_id, self.category, self.channel)
        self.assertEqual(len(result), 2)
        #time.sleep(3)
        #result, error = yield self.store.get_presence(self.project_id, self.category, self.channel)
        #self.assertEqual(result, [])


if __name__ == '__main__':
    main()