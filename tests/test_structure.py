# coding: utf-8
from __future__ import print_function
from tornado.testing import AsyncTestCase, main
import os
import sys

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)

from centrifuge.structure import flatten


class FlattenTest(AsyncTestCase):

    def test_non_dict(self):
        structure = "test"
        self.assertEqual(flatten(structure), "test")

    def test_dict_with_no_options(self):
        structure = {"name": 1}
        self.assertEqual(flatten(structure), structure)

    def test_json_options(self):
        structure = {
            "name": 1,
            "options": '{"test": 1}'
        }
        res = flatten(structure)
        self.assertTrue("name" in res)
        self.assertTrue("test" in res)
        self.assertTrue("options" not in res)

    def test_dict_options(self):
        structure = {
            "name": 1,
            "options": {
                "test": 1
            }
        }
        res = flatten(structure)
        self.assertTrue("name" in res)
        self.assertTrue("test" in res)
        self.assertTrue("options" not in res)


if __name__ == '__main__':
    main()
