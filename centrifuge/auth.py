# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

from centrifuge.utils import json_decode
import hmac
import six
from hashlib import md5, sha256

from centrifuge.log import logger


def detect_hash_algorithm(hash_string):
    hash_string_length = len(hash_string)
    if hash_string_length == 64:
        return sha256
    elif hash_string_length == 32:
        return md5
    return None


def check_sign(secret_key, project_id, encoded_data, auth_sign):
    """
    Check that data from client was properly signed.
    To do it create an HMAC with md5 hashing algorithm (python's default)
    based on secret key, project ID and encoded data and compare result
    with sign provided.
    """
    hash_algorithm = detect_hash_algorithm(auth_sign)
    if not hash_algorithm:
        return False
    sign = hmac.new(six.b(str(secret_key)), digestmod=hash_algorithm)
    sign.update(six.b(project_id))
    sign.update(six.b(encoded_data))
    return sign.hexdigest() == auth_sign


def decode_data(data):
    """
    Decode request body received from API client.
    """
    try:
        return json_decode(data)
    except Exception as err:
        logger.debug(err)
        return None


def get_client_token(secret_key, project_id, user, expired, user_info=None, hash_algorithm=None):
    """
    When client from browser connects to Centrifuge he must send his
    user ID, ID of project and optionally user_info JSON string.
    To validate that data we use md5 HMAC to build token.
    """
    hash_algorithm = hash_algorithm or sha256
    sign = hmac.new(six.b(str(secret_key)), digestmod=hash_algorithm)
    sign.update(six.b(project_id))
    sign.update(six.b(user))
    sign.update(six.b(expired))
    if user_info is not None:
        sign.update(six.b(user_info))
    token = sign.hexdigest()
    return token


def check_client_token(token, secret_key, project_id, user, expired, user_info=None):
    hash_algorithm = detect_hash_algorithm(token)
    if not hash_algorithm:
        return False
    client_token = get_client_token(secret_key, project_id, user, expired, user_info, hash_algorithm=hash_algorithm)
    return token == client_token
