# coding: utf-8
from __future__ import print_function
from tornado.gen import coroutine, Return
from tornado.testing import AsyncTestCase, gen_test
import json

from centrifuge.client import Client
from centrifuge.schema import client_api_schema
from centrifuge.core import Application
from centrifuge.engine.memory import Engine


class FakeSession(object):

    transport_name = 'test'


class FakeSock(object):

    session = FakeSession()

    @coroutine
    def send(self, message):
        return True


class FakeEngine(Engine):

    @coroutine
    def add_presence(self, *args, **kwargs):
        raise Return((True, None))

    @coroutine
    def remove_presence(self, *args, **kwargs):
        raise Return((True, None))


class FakeApplication(Application):

    @coroutine
    def get_project(self, project_id):
        raise Return(({'_id': 'test', 'name': 'test'}, None))

    @coroutine
    def get_namespace(self, project, params):
        raise Return(({'_id': 'test', 'name': 'test'}, None))


class FakePeriodic(object):

    def stop(self):
        return True


class TestClient(Client):

    @coroutine
    def handle_test(self, params):
        raise Return((True, None))


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
        self.client.application = FakeApplication()
        self.client.application.engine = FakeEngine(self.client.application)

    @gen_test
    def test_method_resolve(self):
        message = json.dumps({
            "method": "test",
            "params": {}
        })
        client_api_schema["test"] = {
            "type": "object"
        }
        result, error = yield self.client.message_received(message)
        self.assertEqual(result, True)
        self.assertEqual(error, None)

    @gen_test
    def test_client(self):

        params = {
            "channel": "test"
        }
        result, error = yield self.client.handle_subscribe(params)
        self.assertEqual(result, {"channel": "test"})
        self.assertEqual(error, None)

        subs = self.client.application.engine.subscriptions
        subscription = self.client.application.engine.get_subscription_key(
            self.client.project_id, params["channel"]
        )
        self.assertTrue(subscription in subs)

        self.assertTrue(params["channel"] in self.client.channels)

        result, error = yield self.client.handle_unsubscribe(params)
        self.assertEqual(result, {"channel": "test"})
        self.assertEqual(error, None)
        self.assertTrue(subscription not in subs)

        self.assertTrue(params["channel"] not in self.client.channels)

        result, error = yield self.client.clean()
        self.assertEqual(result, True)
        self.assertEqual(error, None)
