# coding: utf-8
import json
import time
from unittest import TestCase, main

from centrifuge.auth import get_client_token, check_sign, check_channel_sign, check_client_token


class AuthTest(TestCase):

    def setUp(self):
        self.data = 'test'
        self.encoded_data = json.dumps(self.data)

        self.secret = "test"
        self.project_id = "test"
        self.user_id = "test"
        self.user_info = '{"data": "test"}'

    def test_check_sign(self):
        res = check_sign(self.secret, self.project_id, self.encoded_data, 'w')
        self.assertEqual(res, False)
        res = check_sign(self.secret, self.project_id, self.encoded_data, 'w'*32)
        self.assertEqual(res, False)
        res = check_sign(self.secret, self.project_id, self.encoded_data, 'w'*64)
        self.assertEqual(res, False)

    def test_client_token(self):
        now = int(time.time())
        token_no_info = get_client_token(
            self.secret, self.project_id, self.user_id, str(now)
        )
        token_with_info = get_client_token(
            self.secret, self.project_id, self.user_id, str(now), user_info=self.user_info
        )
        self.assertTrue(token_no_info != token_with_info)

    def test_check_client_token(self):
        res = check_client_token('w', self.secret, 'test', 'test', 'test', user_info="")
        self.assertEqual(res, False)

        res = check_client_token('w'*32, self.secret, 'test', 'test', 'test', user_info="")
        self.assertEqual(res, False)

        res = check_client_token('w'*64, self.secret, 'test', 'test', 'test', user_info="")
        self.assertEqual(res, False)

    def test_check_channel_sign(self):
        res = check_channel_sign('w', self.secret, 'test', 'channel', 'channel data')
        self.assertEqual(res, False)

        res = check_channel_sign('w'*32, self.secret, 'test', 'channel', 'channel data')
        self.assertEqual(res, False)

        res = check_channel_sign('w'*64, self.secret, 'test', 'channel', 'channel data')
        self.assertEqual(res, False)


if __name__ == '__main__':
    main()
