# coding: utf-8
from unittest import TestCase, main
import sys
import os

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)

from centrifuge.rpc import *


class RpcTest(TestCase):

    def setUp(self):

        self.project_id = 'countries'
        self.category_id = 'england'
        self.channel = 'liverpool'

    def test_channel_name(self):
        prepared_channel = create_channel_name(
            self.project_id, self.category_id, self.channel
        )
        project_id, category_id, channel = parse_channel_name(prepared_channel)

        self.assertEqual(project_id, self.project_id)
        self.assertEqual(category_id, self.category_id)
        self.assertEqual(channel, self.channel)

    def test_project_channel_name(self):
        prepared_channel = create_project_channel_name(
            self.project_id
        )
        project_id = parse_project_channel_name(prepared_channel)

        self.assertEqual(project_id, self.project_id)


if __name__ == '__main__':
    main()