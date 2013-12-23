# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.gen import coroutine, Return
from centrifuge.structure import BaseStorage


class Storage(BaseStorage):

    NAME = "Config"

    def __init__(self, *args, **kwargs):
        super(Storage, self).__init__(*args, **kwargs)
        self._cursor = None

    def connect(self, callback=None):
        callback()

    @coroutine
    def project_list(self):
        projects = self.settings.get('projects', [])
        raise Return((projects, None))


    @coroutine
    def namespace_list(self):
        namespaces = self.settings.get('namespaces', [])
        raise Return((namespaces, None))