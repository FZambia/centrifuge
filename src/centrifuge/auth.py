# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.escape import json_decode
import base64
import hmac
import six


def check_sign(secret_key, project_id, encoded_data, auth_sign):
    """
    Check that data from client was properly signed.
    """
    sign = hmac.new(six.b(str(secret_key)))
    sign.update(six.b(project_id))
    sign.update(six.b(encoded_data))
    return sign.hexdigest() == auth_sign


def decode_data(data):
    """
    Decode string received from client.
    """
    try:
        return json_decode(base64.b64decode(data))
    except:
        return None


def get_client_token(secret_key, project_id, user):
    """
    Create token to validate information provided by new connection.
    """
    sign = hmac.new(six.b(str(secret_key)))
    sign.update(six.b(user))
    sign.update(six.b(str(project_id)))
    token = sign.hexdigest()
    return token
