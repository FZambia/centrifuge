# coding: utf-8
import json
import time
from unittest import TestCase, main

from centrifuge.auth import get_client_token, check_sign, check_channel_sign


class AuthTest(TestCase):

    def setUp(self):
        self.data = 'test'
        self.encoded_data = json.dumps(self.data)

        self.secret_key = "test"
        self.project_id = "test"
        self.user_id = "test"
        self.user_info = '{"data": "test"}'

    def test_check_sign(self):
        res = check_sign(self.secret_key, self.project_id, self.encoded_data, 'wrong sign')
        self.assertEqual(res, False)

    def test_client_token(self):
        now = int(time.time())
        token_no_info = get_client_token(
            self.secret_key, self.project_id, self.user_id, str(now)
        )
        token_with_info = get_client_token(
            self.secret_key, self.project_id, self.user_id, str(now), user_info=self.user_info
        )
        self.assertTrue(token_no_info != token_with_info)

    def test_channel_sign(self):
        res = check_channel_sign('w', self.secret_key, 'test', 'channel', 'channel data')
        self.assertEqual(res, False)

        res = check_channel_sign('w'*64, self.secret_key, 'test', 'channel', 'channel data')
        self.assertEqual(res, False)


if __name__ == '__main__':
    main()
