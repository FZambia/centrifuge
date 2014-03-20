# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import json
from tornado.gen import coroutine, Return
from centrifuge.structure import BaseStorage


from tornado.options import define

define(
    "path", default='structure.json', help="Path to JSON file with structure configuration", type=str
)


class Storage(BaseStorage):

    NAME = "JSON file"

    def __init__(self, *args, **kwargs):
        super(Storage, self).__init__(*args, **kwargs)
        self.data = json.load(open(self.options.path, 'r'))

    def connect(self, callback=None):
        callback()

    @coroutine
    def project_list(self):
        projects = self.data.get('projects', [])
        raise Return((projects, None))

    @coroutine
    def namespace_list(self):
        namespaces = self.data.get('namespaces', [])
        raise Return((namespaces, None))
