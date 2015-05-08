# coding: utf-8
from unittest import main, TestCase
from tornado.testing import gen_test
from mock import Mock
import socket

from centrifuge.core import *


class TestApp(Application):
    pass


class CoreTest(TestCase):

    def setUp(self):
        self.app = TestApp()
        self.app.structure = Mock()

    def test_get_address(self):
        mock = Mock(return_value='x')
        socket.gethostname = mock
        self.assertEqual(get_address(), 'x')

    def test_extracting_namespace(self):

        channel = 'channel'
        self.assertEqual(self.app.extract_namespace_name(channel), None)

        channel = 'namespace:channel'
        self.assertEqual(self.app.extract_namespace_name(channel), 'namespace')

        channel = 'namespace:channel#user1,user2'
        self.assertEqual(self.app.extract_namespace_name(channel), 'namespace')

        channel = '$namespace:channel'
        self.assertEqual(self.app.extract_namespace_name(channel), 'namespace')

    def test_get_allowed_users(self):

        channel = 'namespace:channel#2'
        self.assertEqual(self.app.get_allowed_users(channel), ['2'])

        channel = 'channel#1,34'
        self.assertEqual(self.app.get_allowed_users(channel), ['1', '34'])

    def test_is_channel_private(self):
        channel = "channel"
        self.assertEqual(self.app.is_channel_private(channel), False)

        channel = "$channel"
        self.assertEqual(self.app.is_channel_private(channel), True)

if __name__ == '__main__':
    main()
