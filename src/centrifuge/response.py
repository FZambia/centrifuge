# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.escape import json_encode


class Response(object):

    def __init__(self, uid=None, method=None, params=None, error=None, body=None):
        self.uid = uid
        self.method = method
        self.params = params
        self.error = error
        self.body = body

    def as_message(self):
        return json_encode(self.as_dict())

    def as_dict(self):
        return {
            'uid': self.uid,
            'method': self.method,
            'params': self.params,
            'error': self.error,
            'body': self.body
        }