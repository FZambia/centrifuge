# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.gen import coroutine, Return


NAME = "Config"


def init_storage(structure, settings, callback):
    """
    Use settings as database
    """
    structure.set_db(settings)
    structure.set_consistency(True)
    callback()


@coroutine
def project_list(db):
    projects = db.get('projects', [])
    raise Return((projects, None))


@coroutine
def namespace_list(db):
    namespaces = db.get('namespaces', [])
    raise Return((namespaces, None))