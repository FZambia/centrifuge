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
        socket.gethostbyname = mock
        self.assertEqual(get_address(), 'x')

    def test_extracting_namespace(self):

        channel = 'channel'
        self.assertEqual(self.app.extract_namespace_name(channel), None)

        channel = 'namespace:channel'
        self.assertEqual(self.app.extract_namespace_name(channel), 'namespace')

        channel = 'namespace:channel#user1,user2'
        self.assertEqual(self.app.extract_namespace_name(channel), 'namespace')


if __name__ == '__main__':
    main()
