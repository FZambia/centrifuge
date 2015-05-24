# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import hmac
import six
from hashlib import sha256


def check_sign(secret, project_name, encoded_data, auth_sign):
    """
    Check that data from client was properly signed.
    To do it create an HMAC with sha256 hashing algorithm
    based on secret key, project name and encoded data and compare result
    with sign provided.
    """
    sign = hmac.new(six.b(str(secret)), digestmod=sha256)
    sign.update(six.b(project_name))
    sign.update(six.b(encoded_data))
    return sign.hexdigest() == auth_sign


def get_client_token(secret, project_name, user, timestamp, user_info=""):
    """
    When client from browser connects to Centrifuge he must send his
    user ID, name of project and optionally user_info JSON string.
    To validate that data we use HMAC to build token.
    """
    sign = hmac.new(six.b(str(secret)), digestmod=sha256)
    sign.update(six.b(project_name))
    sign.update(six.b(user))
    sign.update(six.b(timestamp))
    sign.update(six.b(user_info))
    token = sign.hexdigest()
    return token


def check_client_token(token, secret, project_name, user, timestamp, user_info=""):
    """
    Create reference token based on connection parameters and
    compare it with token provided by client
    """
    client_token = get_client_token(secret, project_name, user, timestamp, user_info)
    return token == client_token


def check_channel_sign(provided_sign, secret, client_id, channel, channel_data):
    """
    Create reference sign and compare it with sign provided
    by client subscribing on private channel
    """
    sign = hmac.new(six.b(str(secret)), digestmod=sha256)
    sign.update(six.b(client_id))
    sign.update(six.b(channel))
    sign.update(six.b(channel_data))
    return sign.hexdigest() == provided_sign
