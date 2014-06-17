# coding: utf-8
import json
import time
from unittest import TestCase, main

from centrifuge.utils import *


class FakeForm(object):
    pass


class UtilsTest(TestCase):

    def setUp(self):
        pass

    def test_make_patch_data(self):
        form = FakeForm()
        form.data = {"test": 1, "opa": 2}
        params = {"test": 2}
        data = make_patch_data(form, params)
        self.assertEqual(data, {"test": 1})

    def test_get_boolean_patch_data(self):
        boolean_fields = ['test']
        params = {'test': 0}
        data = get_boolean_patch_data(boolean_fields, params)
        self.assertEqual(data, {'test': False})


if __name__ == '__main__':
    main()
