# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import sqlite3
from tornado.gen import coroutine, Return
import uuid
from bson import ObjectId
from ..log import logger


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def on_error(error):
    """
    General error wrapper.
    """
    logger.error(str(error))
    raise Return((None, error))


def init_storage(structure, settings, ready_callback):
    conn = sqlite3.connect(settings.get('path', 'centrifuge.db'))
    # noinspection PyPropertyAccess
    conn.row_factory = dict_factory
    cursor = conn.cursor()

    project = 'CREATE TABLE IF NOT EXISTS projects (id SERIAL, _id varchar(24) UNIQUE, ' \
              'name varchar(100) NOT NULL UNIQUE, display_name ' \
              'varchar(100) NOT NULL, auth_address varchar(255), ' \
              'max_auth_attempts integer, back_off_interval integer, ' \
              'back_off_max_timeout integer, secret_key varchar(32), ' \
              'default_namespace varchar(32))'

    namespace = 'CREATE TABLE IF NOT EXISTS namespaces (id SERIAL, ' \
                '_id varchar(24) UNIQUE, project_id varchar(24), ' \
                'name varchar(100) NOT NULL, ' \
                'publish bool, is_watching bool, presence bool, history bool, ' \
                'history_size integer, is_private bool, auth_address varchar(255), join_leave bool, ' \
                'UNIQUE (project_id, name) ON CONFLICT ABORT)'

    cursor.execute(project, ())
    conn.commit()
    cursor.execute(namespace, ())
    conn.commit()

    structure.set_db(cursor)
    ready_callback()
    logger.info("Database ready")


def extract_obj_id(obj):
    if isinstance(obj, dict):
        obj_id = obj['_id']
    else:
        obj_id = obj
    return obj_id


@coroutine
def project_list(cursor):
    """
    Get all projects user can see.
    """
    query = "SELECT * FROM projects"
    try:
        cursor.execute(query, {},)
    except Exception as e:
        on_error(e)
    else:
        projects = cursor.fetchall()
        raise Return((projects, None))


@coroutine
def project_create(cursor, **kwargs):

    to_insert = (
        str(ObjectId()),
        kwargs['name'],
        kwargs['display_name'],
        kwargs['auth_address'],
        kwargs['max_auth_attempts'],
        kwargs['back_off_interval'],
        kwargs['back_off_max_timeout'],
        uuid.uuid4().hex,
        None
    )

    query = "INSERT INTO projects (_id, name, display_name, " \
            "auth_address, max_auth_attempts, back_off_interval, back_off_max_timeout, " \
            "secret_key, default_namespace) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)"

    try:
        cursor.execute(query, to_insert)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_insert, None))


@coroutine
def project_edit(cursor, project, **kwargs):
    """
    Edit project
    """
    to_return = {
        '_id': extract_obj_id(project),
        'name': kwargs['name'],
        'display_name': kwargs['display_name'],
        'auth_address': kwargs['auth_address'],
        'max_auth_attempts': kwargs['max_auth_attempts'],
        'back_off_interval': kwargs['back_off_interval'],
        'back_off_max_timeout': kwargs['back_off_max_timeout'],
        'default_namespace': kwargs['default_namespace']
    }

    to_update = (
        kwargs['name'], kwargs['display_name'], kwargs['auth_address'],
        kwargs['max_auth_attempts'], kwargs['back_off_interval'],
        kwargs['back_off_max_timeout'], to_return['default_namespace'],
        extract_obj_id(project)
    )

    query = "UPDATE projects SET name=?, display_name=?, auth_address=?, " \
            "max_auth_attempts=?, back_off_interval=?, back_off_max_timeout=?, " \
            "default_namespace=? WHERE _id=?"

    try:
        cursor.execute(query, to_update)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_return, None))


@coroutine
def project_delete(cursor, project):
    """
    Delete project. Also delete all related namespaces and events.
    """
    haystack = (project['_id'], )

    query = "DELETE FROM projects WHERE _id=?"
    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)

    query = "DELETE FROM namespaces WHERE project_id=?"
    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((True, None))


@coroutine
def namespace_list(cursor):
    """
    Get all namespaces
    """
    query = "SELECT * FROM namespaces"
    try:
        cursor.execute(query, ())
    except Exception as e:
        on_error(e)
    else:
        namespaces = cursor.fetchall()
        raise Return((namespaces, None))


@coroutine
def namespace_create(cursor, project, **kwargs):

    to_return = {
        '_id': str(ObjectId()),
        'project_id': project['_id'],
        'name': kwargs['name'],
        'publish': kwargs['publish'],
        'is_watching': kwargs['is_watching'],
        'presence': kwargs['presence'],
        'history': kwargs['history'],
        'history_size': kwargs['history_size'],
        'is_private': kwargs['is_private'],
        'auth_address': kwargs['auth_address'],
        'join_leave': kwargs['join_leave']
    }

    to_insert = (
        to_return['_id'], to_return['project_id'], to_return['name'], to_return['publish'],
        to_return['is_watching'], to_return['presence'], to_return['history'],
        to_return['history_size'], to_return['is_private'], to_return['auth_address'],
        to_return['join_leave']
    )

    query = "INSERT INTO namespaces (_id, project_id, name, publish, " \
            "is_watching, presence, history, history_size, is_private, " \
            "auth_address, join_leave) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"

    try:
        cursor.execute(query, to_insert)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_insert, None))


@coroutine
def namespace_edit(cursor, namespace, **kwargs):
    """
    Edit project
    """
    to_return = {
        '_id': namespace['_id'],
        'name': kwargs['name'],
        'publish': kwargs['publish'],
        'is_watching': kwargs['is_watching'],
        'presence': kwargs['presence'],
        'history': kwargs['history'],
        'history_size': kwargs['history_size'],
        'is_private': kwargs['is_private'],
        'auth_address': kwargs['auth_address'],
        'join_leave': kwargs['join_leave']
    }

    to_update = (
        to_return['name'], to_return['publish'], to_return['is_watching'],
        to_return['presence'], to_return['history'], to_return['history_size'],
        to_return['is_private'], to_return['auth_address'], to_return['join_leave'],
        namespace['_id']
    )

    query = "UPDATE namespaces SET name=?, publish=?, is_watching=?, presence=?, " \
            "history=?, history_size=?, is_private=?, auth_address=?, join_leave=? " \
            "WHERE _id=?"

    try:
        cursor.execute(query, to_update)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_return, None))


@coroutine
def namespace_delete(cursor, project, namespace_name):
    """
    Delete namespace from project. Also delete all related entries from
    event collection.
    """
    haystack = (namespace_name, project['_id'])
    query = "DELETE FROM namespaces WHERE name=? AND project_id=?"
    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((True, None))


@coroutine
def regenerate_project_secret_key(cursor, project):
    """
    Create new secret and public keys for user in specified project.
    """
    project_id = extract_obj_id(project)
    secret_key = uuid.uuid4().hex
    haystack = (secret_key, project_id)

    query = "UPDATE projects SET secret_key=? WHERE _id=?"

    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((secret_key, None))


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
        if namespace['project_id'] not in to_return:
            to_return[namespace['project_id']] = {}
        to_return[namespace['project_id']][namespace['name']] = namespace
    return to_return


def project_namespaces(namespaces):
    to_return = {}
    for namespace in namespaces:
        if namespace['project_id'] not in to_return:
            to_return[namespace['project_id']] = []
        to_return[namespace['project_id']].append(namespace)
    return to_return