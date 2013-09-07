# coding: utf-8
import sys
import os
import json
import base64
from unittest import TestCase, main

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)


from centrifuge.auth import decode_data


class AuthTest(TestCase):

    def setUp(self):

        class FakeRequest(object):
            pass

        self.correct_request = FakeRequest()
        self.wrong_request = FakeRequest()
        self.wrong_request.headers = {}
        self.data = 'test'
        self.encoded_data = base64.b64encode(json.dumps(self.data))

    def test_decode_data(self):
        self.assertEqual(decode_data(self.encoded_data), self.data)


if __name__ == '__main__':
    main()