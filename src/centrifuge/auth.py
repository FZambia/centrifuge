# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
from tornado.escape import json_decode
import base64
import hmac
import zlib


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

