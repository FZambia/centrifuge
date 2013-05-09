# coding: utf-8
import sys
import os
import zlib
import json
import base64
from unittest import TestCase, main

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)

from centrifuge.auth import AUTH_HEADER_NAME
from centrifuge.auth import parse_auth_header
from centrifuge.auth import get_auth_header
from centrifuge.auth import decode_data


class AuthTest(TestCase):

    def setUp(self):

        class FakeRequest(object):
            pass

        self.correct_request = FakeRequest()
        self.auth_header_data = "public_key=qwerty sign=123"
        self.correct_request.headers = {
            AUTH_HEADER_NAME: self.auth_header_data
        }

        self.wrong_request = FakeRequest()
        self.wrong_request.headers = {}

        self.data = 'test'
        self.encoded_data = zlib.compress(base64.b64encode(json.dumps(self.data)))

    def test_get_auth_header(self):
        self.assertEqual(
            get_auth_header(self.correct_request),
            self.auth_header_data
        )
        self.assertEqual(get_auth_header(self.wrong_request), None)

    def test_parse_auth_header(self):
        parsed_data = parse_auth_header(self.auth_header_data)
        self.assertTrue(isinstance(parsed_data, dict))
        self.assertEqual(len(parsed_data), 2)
        self.assertEqual(parsed_data['public_key'], 'qwerty')
        self.assertEqual(parsed_data['sign'], '123')

    def test_decode_data(self):
        self.assertEqual(decode_data(self.encoded_data), self.data)


if __name__ == '__main__':
    main()