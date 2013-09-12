# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.gen import coroutine, Return


def init_storage(structure, settings, callback):
    """
    Use settings as database
    """
    structure.set_db(settings)
    callback()


@coroutine
def project_list(db):
    """
    Get all projects
    """
    projects = db.get('projects', [])
    raise Return((projects, None))


@coroutine
def namespace_list(db):
    """
    Get all namespaces
    """
    namespaces = db.get('namespaces', [])
    raise Return((namespaces, None))


def projects_by_id(projects):
    to_return = {}
    for project in projects:
        to_return[project['_id']] = project
    return to_return


def projects_by_name(projects):
    to_return = {}
    for project in projects:
        to_return[project['name']] = project
    return to_return


def namespaces_by_id(namespaces):
    to_return = {}
    for namespace in namespaces:
        to_return[namespace['_id']] = namespace
    return to_return


def namespaces_by_name(namespaces):
    to_return = {}
    for namespace in namespaces:
        if namespace['project'] not in to_return:
            to_return[namespace['project']] = {}
        to_return[namespace['project']][namespace['name']] = namespace
    return to_return


def project_namespaces(namespaces):
    to_return = {}
    for namespace in namespaces:
        if namespace['project'] not in to_return:
            to_return[namespace['project']] = []
        to_return[namespace['project']].append(namespace)
    return to_return