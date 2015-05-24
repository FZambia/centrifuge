# coding: utf-8
import json
import time
from unittest import TestCase, main

from centrifuge.response import *


class ResponseTest(TestCase):

    def setUp(self):
        pass

    def test_response(self):
        response = Response(method='test_method', error='test_error', body='test_body')
        self.assertEqual(response.method, 'test_method')
        self.assertEqual(response.error, 'test_error')
        self.assertEqual(response.body, 'test_body')

        response_dict = response.as_dict()
        self.assertTrue('method' in response_dict)
        self.assertTrue('error' in response_dict)
        self.assertTrue('body' in response_dict)

        response_message = response.as_message()
        response = json.loads(response_message)
        self.assertEqual(response["method"], "test_method")
        self.assertEqual(response["error"], "test_error")
        self.assertEqual(response["body"], "test_body")


class MultiResponseTest(TestCase):

    def setUp(self):
        pass

    def test_response(self):
        response_1 = Response(method='test_method1', error='test_error1', body='test_body1')
        response_2 = Response(method='test_method2', error='test_error2', body='test_body2')
        
        multi_response = MultiResponse()
        multi_response.add(response_1)
        self.assertEqual(len(multi_response.responses), 1)

        multi_response.add_many([response_2])
        self.assertEqual(len(multi_response.responses), 2)

        response_list = multi_response.as_list_of_dicts()
        self.assertTrue(isinstance(response_list, list))
        self.assertTrue(len(response_list), 2)

        response_message = multi_response.as_message()
        response = json.loads(response_message)[0]
        self.assertEqual(response["method"], "test_method1")
        self.assertEqual(response["error"], "test_error1")
        self.assertEqual(response["body"], "test_body1")

        response = json.loads(response_message)[1]
        self.assertEqual(response["method"], "test_method2")
        self.assertEqual(response["error"], "test_error2")
        self.assertEqual(response["body"], "test_body2")


if __name__ == '__main__':
    main()
