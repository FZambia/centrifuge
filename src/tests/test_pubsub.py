# coding: utf-8
from unittest import TestCase, main
import sys
import os

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)

from centrifuge.pubsub.base import BasePubSub
from centrifuge.core import Application


class FakeClient(object):

    uid = 'test'


class CoreTest(TestCase):

    def setUp(self):
        self.application = Application()
        self.pubsub = BasePubSub(self.application)

        self.project_id = 'test'
        self.namespace = 'test'
        self.channel = 'test'

    def test_get_subscription_key(self):
        subscription_key = self.pubsub.get_subscription_key(
            self.project_id, self.namespace, self.channel
        )
        self.assertTrue(isinstance(subscription_key, str))

    def test_add_subscription(self):
        self.pubsub.add_subscription(self.project_id, self.namespace, self.channel, FakeClient())

        self.assertTrue(
            self.pubsub.get_subscription_key(
                self.project_id, self.namespace, self.channel
            ) in self.pubsub.subscriptions
        )

    def test_remove_subscription(self):
        self.pubsub.remove_subscription(self.project_id, self.namespace, self.channel, FakeClient())

        self.assertTrue(
            self.pubsub.get_subscription_key(
                self.project_id, self.namespace, self.channel
            ) not in self.pubsub.subscriptions
        )


if __name__ == '__main__':
    main()