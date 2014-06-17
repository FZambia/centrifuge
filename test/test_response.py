# coding: utf-8
import json
import time
from unittest import TestCase, main

from centrifuge.response import *


class ResponseTest(TestCase):

    def setUp(self):
        pass

    def test_response(self):
        response = Response(uid='test_uid', method='test_method', error='test_error', body='test_body')
        self.assertEqual(response.uid, 'test_uid')
        self.assertEqual(response.method, 'test_method')
        self.assertEqual(response.error, 'test_error')
        self.assertEqual(response.body, 'test_body')

        response_dict = response.as_dict()
        self.assertTrue('uid' in response_dict)
        self.assertTrue('method' in response_dict)
        self.assertTrue('error' in response_dict)
        self.assertTrue('body' in response_dict)

        response_message = response.as_message()
        self.assertEqual(response_message, json.dumps(response_dict))


class MultiResponseTest(TestCase):

    def setUp(self):
        pass

    def test_response(self):
        response_1 = Response(uid='test_uid', method='test_method', error='test_error', body='test_body')
        response_2 = Response(uid='test_uid', method='test_method', error='test_error', body='test_body')
        
        multi_response = MultiResponse()
        multi_response.add(response_1)
        self.assertEqual(len(multi_response.responses), 1)

        multi_response.add_many([response_2])
        self.assertEqual(len(multi_response.responses), 2)

        response_list = multi_response.as_list_of_dicts()
        self.assertTrue(isinstance(response_list, list))
        self.assertTrue(len(response_list), 2)

        response_message = multi_response.as_message()
        self.assertEqual(response_message, json.dumps(response_list))


if __name__ == '__main__':
    main()
