# coding: utf-8
import sys
import os
import json
from unittest import TestCase, main

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)


from centrifuge.auth import decode_data, get_client_token


class AuthTest(TestCase):

    def setUp(self):

        class FakeRequest(object):
            pass

        self.correct_request = FakeRequest()
        self.wrong_request = FakeRequest()
        self.wrong_request.headers = {}
        self.data = 'test'
        self.encoded_data = json.dumps(self.data)
        self.secret_key = "test"
        self.project_id = "test"
        self.user_id = "test"
        self.user_info = '{"data": "test"}'

    def test_decode_data(self):
        self.assertEqual(decode_data(self.encoded_data), self.data)

    def test_client_token(self):
        token_no_info = get_client_token(
            self.secret_key, self.project_id, self.user_id
        )
        token_with_info = get_client_token(
            self.secret_key, self.project_id, self.user_id, user_info=self.user_info
        )
        self.assertTrue(token_no_info != token_with_info)

if __name__ == '__main__':
    main()
