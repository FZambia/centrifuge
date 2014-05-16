# coding: utf-8
from unittest import TestCase, main


from centrifuge.core import *


class TestApp(Application):
    pass


class CoreTest(TestCase):

    def setUp(self):
        self.app = TestApp()

    def test_extracting_namespace(self):

        channel = 'channel'
        self.assertEqual(self.app.extract_namespace_name(channel), None)

        channel = 'namespace:channel'
        self.assertEqual(self.app.extract_namespace_name(channel), 'namespace')

        channel = 'namespace:channel#user1.user2'
        self.assertEqual(self.app.extract_namespace_name(channel), 'namespace')


if __name__ == '__main__':
    main()
