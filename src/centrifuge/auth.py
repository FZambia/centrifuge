# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
from tornado.escape import json_decode
import base64
import hmac
import six


AUTH_HEADER_NAME = 'X-Centrifuge-Auth'


def get_client_token(secret_key, project_id, user):
    """
    Create token to validate information provided by new connection.
    """
    sign = hmac.new(six.b(str(secret_key)))
    sign.update(six.b(user))
    sign.update(six.b(str(project_id)))
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
    sign = hmac.new(six.b(str(secret_key)))
    sign.update(six.b(project_id))
    sign.update(encoded_data)
    return sign.hexdigest() == auth_sign


def decode_data(data):
    """
    Decode string received from client.
    """
    try:
        return json_decode(base64.b64decode(data))
    except BaseException:
        return None
