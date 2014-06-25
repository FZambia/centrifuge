# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

from centrifuge.utils import json_encode


class Response(object):

    def __init__(self, uid=None, method=None, error=None, body=None):
        self.uid = uid
        self.method = method
        self.error = error
        self.body = body

    def as_message(self):
        return json_encode(self.as_dict())

    def as_dict(self):
        return {
            'uid': self.uid,
            'method': self.method,
            'error': self.error,
            'body': self.body
        }


class MultiResponse(object):

    def __init__(self):
        self.responses = []

    def add(self, response):
        self.responses.append(response)

    def add_many(self, responses):
        for response in responses:
            self.add(response)

    def as_message(self):
        return json_encode(self.as_list_of_dicts())

    def as_list_of_dicts(self):
        return [x.as_dict() for x in self.responses]
