# coding: utf-8
from __future__ import print_function
from tornado.gen import Task, coroutine, Return
from tornado.testing import AsyncTestCase, gen_test
from centrifuge.client import Client
from centrifuge.schema import client_api_schema
from centrifuge.core import Application
from centrifuge.pubsub.base import BasePubSub
import json


class FakeSock(object):

    def send(self, message):
        return True


class FakeState(object):

    @coroutine
    def add_presence(self, *args, **kwargs):
        raise Return((True, None))

    @coroutine
    def remove_presence(self, *args, **kwargs):
        raise Return((True, None))


class FakePeriodic(object):

    def stop(self):
        return True


class TestClient(Client):

    @coroutine
    def handle_test(self, params):
        raise Return((True, None))

    @coroutine
    def get_project(self, project_id):
        raise Return(({'_id': 'test', 'name': 'test'}, None))

    @coroutine
    def get_namespace(self, project, params):
        raise Return(({'_id': 'test', 'name': 'test'}, None))


class ClientTest(AsyncTestCase):
    """ Test the client """

    def setUp(self):
        super(ClientTest, self).setUp()
        self.client = TestClient(FakeSock(), {})
        self.client.is_authenticated = True
        self.client.project_id = "test_project"
        self.client.uid = "test_uid"
        self.client.user = "test_user"
        self.client.channels = {}
        self.client.presence_ping = FakePeriodic()
        self.client.application = Application()
        self.client.application.pubsub = BasePubSub(self.client.application)
        self.client.application.state = FakeState()

    @gen_test
    def test_method_resolve(self):
        message = json.dumps({
            "method": "test",
            "params": {}
        })
        result, error = yield self.client.message_received(message)
        self.assertTrue(error is not None)

        client_api_schema["test"] = {
            "type": "object"
        }
        result, error = yield self.client.message_received(message)
        self.assertEqual(result, True)
        self.assertEqual(error, None)

    @gen_test
    def test_client(self):

        params = {
            "namespace": "test"
        }
        result, error = yield self.client.handle_subscribe(params)
        self.assertTrue(error is not None)

        params = {
            "namespace": "test",
            "channel": "test"
        }
        result, error = yield self.client.handle_subscribe(params)
        self.assertEqual(result, True)
        self.assertEqual(error, None)

        conns = self.client.application.connections
        self.assertTrue(self.client.project_id in conns)
        self.assertTrue(self.client.user in conns[self.client.project_id])
        self.assertTrue(self.client.uid in conns[self.client.project_id][self.client.user])

        subs = self.client.application.pubsub.subscriptions
        subscription = self.client.application.pubsub.get_subscription_key(
            self.client.project_id, params["namespace"], params["channel"]
        )
        self.assertTrue(subscription in subs)

        self.assertTrue(params["namespace"] in self.client.channels)
        self.assertTrue(params["channel"] in self.client.channels[params["namespace"]])

        result, error = yield self.client.handle_unsubscribe(params)
        self.assertEqual(result, True)
        self.assertEqual(error, None)
        self.assertTrue(subscription not in subs)

        self.assertTrue(params["namespace"] not in self.client.channels)

        result, error = yield self.client.clean()
        self.assertEqual(result, True)
        self.assertEqual(error, None)
        self.assertTrue(self.client.project_id not in conns)
