# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
from tornado.escape import json_decode
import base64
import hmac
import zlib

import codecs
import json
import re

try:
    from urllib import urlencode
except ImportError:
    # python 3
    from urllib.parse import urlencode

from tornado import httpclient
from tornado.auth import OAuth2Mixin


AUTH_HEADER_NAME = 'X-Centrifuge-Auth'


def create_admin_token(secret, timestamp, user_id, projects):
    """
    Create token to confirm administrator's subscription on project's
    real-time updates.
    """
    token = hmac.new(str(secret))
    token.update(str(timestamp))
    token.update(str(user_id))
    [token.update(project) for project in projects]
    return token.hexdigest()


def get_client_token(secret_key, public_key, user):
    """
    Create token to validate information provided by new connection.
    """
    sign = hmac.new(str(secret_key))
    sign.update(user)
    sign.update(public_key)
    token = sign.hexdigest()
    return token


def get_auth_header(request):
    """
    Get and return authentication header from request.
    """
    return request.headers.get(AUTH_HEADER_NAME, None)


def parse_auth_header(header):
    """
    Parse authentication header and return dictionary or None in case of an error.
    """
    try:
        to_return = dict(
            map(
                lambda x: x.strip().split('='),
                header.split(' ')
            )
        )
    except (IndexError, ValueError):
        return None
    return to_return


def extract_auth_info(request):
    """
    Get authentication credentials from auth data
    """
    auth_header = get_auth_header(request)
    if not auth_header:
        return None, "no auth header found"

    auth_info = parse_auth_header(auth_header)
    if not auth_info:
        return None, "malformed auth header"

    return auth_info, None


def check_sign(secret_key, project_id, encoded_data, auth_sign):
    sign = hmac.new(str(secret_key))
    sign.update(project_id)
    sign.update(encoded_data)
    return sign.hexdigest() == auth_sign


def decode_data(data):
    """
    Decode string received from client.
    """
    try:
        return json_decode(base64.b64decode(zlib.decompress(data)))
    except BaseException:
        return None


class GithubMixin(OAuth2Mixin):
    """GitHub OAuth2 Authentication

    To authenticate with GitHub, first register your application at
    https://github.com/settings/applications/new to get the client ID and
    secret.
    """

    _API_BASE_HEADERS = {
        'Accept': 'application/json',
        'User-Agent': 'Tornado OAuth'
    }
    _OAUTH_ACCESS_TOKEN_URL = 'https://github.com/login/oauth/access_token'
    _OAUTH_AUTHORIZE_URL = 'https://github.com/login/oauth/authorize'
    _OAUTH_USER_URL = 'https://api.github.com/user?access_token='

    def get_authenticated_user(self, redirect_uri, client_id, state,
                               client_secret=None, code=None,
                               success_callback=None,
                               error_callback=None):
        """ Fetches the authenticated user

        :param redirect_uri: the redirect URI
        :param client_id: the client ID
        :param state: the unguessable random string to protect against
                      cross-site request forgery attacks
        :param client_secret: the client secret
        :param code: the response code from the server
        :param success_callback: the success callback used when fetching
                                 the access token succeeds
        :param error_callback: the callback used when fetching the access
                               token fails
        """
        if code:
            self._fetch_access_token(
                code,
                success_callback,
                error_callback,
                redirect_uri,
                client_id,
                client_secret,
                state
            )

            return

        params = {
            'redirect_uri': redirect_uri,
            'client_id':    client_id,
            'extra_params': {
                'state': state
            }
        }

        self.authorize_redirect(**params)

    def _fetch_access_token(self, code, success_callback, error_callback,
                           redirect_uri, client_id, client_secret, state):
        """ Fetches the access token.

        :param code: the response code from the server
        :param success_callback: the success callback used when fetching
                                 the access token succeeds
        :param error_callback: the callback used when fetching the access
                               token fails
        :param redirect_uri: the redirect URI
        :param client_id: the client ID
        :param client_secret: the client secret
        :param state: the unguessable random string to protect against
                      cross-site request forgery attacks
        :return:
        """
        if not (client_secret and success_callback and error_callback):
            raise ValueError(
                'The client secret or any callbacks are undefined.'
            )

        params = {
            'code':          code,
            'redirect_url':  redirect_uri,
            'client_id':     client_id,
            'client_secret': client_secret,
            'state':         state
        }

        http = httpclient.AsyncHTTPClient()

        callback_sharing_data = {}

        def use_error_callback(response, decoded_body):
            data = {
                'code': response.code,
                'body': decoded_body
            }

            if response.error:
                data['error'] = response.error

            error_callback(**data)

        def decode_response_body(response):
            """ Decodes the JSON-format response body

            :param response: the response object
            :type response: tornado.httpclient.HTTPResponse

            :return: the decoded data
            """
            # Fix GitHub response.
            body = codecs.decode(response.body, 'ascii')
            body = re.sub('"', '\"', body)
            body = re.sub("'", '"', body)
            body = json.loads(body)

            if response.error:
                use_error_callback(response, body)

                return None

            return body

        def on_authenticate(response):
            """ The callback handling the authentication

            :param response: the response object
            :type response: tornado.httpclient.HTTPResponse
            """
            body = decode_response_body(response)

            if not body:
                return

            if 'access_token' not in body:
                use_error_callback(response, body)

                return

            callback_sharing_data['access_token'] = body['access_token']

            http.fetch(
                '{}{}'.format(
                    self._OAUTH_USER_URL, callback_sharing_data['access_token']
                ),
                on_fetching_user_information,
                headers=self._API_BASE_HEADERS
            )

        def on_fetching_user_information(response):
            """ The callback handling the data after fetching the user info

            :param response: the response object
            :type response: tornado.httpclient.HTTPResponse
            """
            # Fix GitHub response.
            user = decode_response_body(response)

            if not user:
                return

            success_callback(user, callback_sharing_data['access_token'])

        # Request the access token.
        http.fetch(
            self._OAUTH_ACCESS_TOKEN_URL,
            on_authenticate,
            method='POST',
            body=urlencode(params),
            headers=self._API_BASE_HEADERS
        )
