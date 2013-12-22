# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import sqlite3
from tornado.gen import coroutine, Return
import uuid
import json


NAME = "SQLite"


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def on_error(error):
    raise Return((None, error))


def init_storage(structure, settings, ready_callback):
    conn = sqlite3.connect(settings.get('path', 'centrifuge.db'))
    # noinspection PyPropertyAccess
    conn.row_factory = dict_factory
    cursor = conn.cursor()

    project = 'CREATE TABLE IF NOT EXISTS projects (id INTEGER PRIMARY KEY AUTOINCREMENT, ' \
              '_id varchar(32) UNIQUE, secret_key varchar(32) NOT NULL, options text)'

    namespace = 'CREATE TABLE IF NOT EXISTS namespaces (id INTEGER PRIMARY KEY AUTOINCREMENT, ' \
                '_id varchar(32) UNIQUE, project_id varchar(32), name varchar(100) NOT NULL, ' \
                'options text, UNIQUE (project_id, name) ON CONFLICT ABORT)'

    cursor.execute(project, ())
    conn.commit()
    cursor.execute(namespace, ())
    conn.commit()

    structure.set_db(cursor)
    ready_callback()


@coroutine
def clear_structure(cursor):
    project = "DELETE FROM projects"
    namespace = "DELETE FROM namespaces"
    try:
        cursor.execute(project, ())
        cursor.connection.commit()
        cursor.execute(namespace, ())
        cursor.connection.commit()
    except Exception as err:
        raise Return((None, err))
    raise Return((True, None))


def extract_obj_id(obj):
    return obj['_id']


@coroutine
def project_list(cursor):

    query = "SELECT * FROM projects"
    try:
        cursor.execute(query, {},)
    except Exception as e:
        on_error(e)
    else:
        projects = cursor.fetchall()
        raise Return((projects, None))


@coroutine
def project_create(cursor, secret_key, options, project_id=None):

    to_insert = (
        project_id or uuid.uuid4().hex,
        secret_key,
        json.dumps(options)
    )

    to_return = {
        '_id': to_insert[0],
        'secret_key': to_insert[1],
        'options': to_insert[2]
    }

    query = "INSERT INTO projects (_id, secret_key, options) VALUES (?, ?, ?)"

    try:
        cursor.execute(query, to_insert)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_return, None))


@coroutine
def project_edit(cursor, project, options):

    to_return = {
        '_id': extract_obj_id(project),
        'options': options
    }

    to_update = (json.dumps(options), extract_obj_id(project))

    query = "UPDATE projects SET options=? WHERE _id=?"

    try:
        cursor.execute(query, to_update)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_return, None))


@coroutine
def regenerate_project_secret_key(cursor, project, secret_key):

    project_id = extract_obj_id(project)
    haystack = (secret_key, project_id)

    query = "UPDATE projects SET secret_key=? WHERE _id=?"

    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((secret_key, None))


@coroutine
def project_delete(cursor, project):
    """
    Delete project. Also delete all related namespaces.
    """
    haystack = (extract_obj_id(project), )

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

    query = "SELECT * FROM namespaces"
    try:
        cursor.execute(query, ())
    except Exception as e:
        on_error(e)
    else:
        namespaces = cursor.fetchall()
        raise Return((namespaces, None))


@coroutine
def namespace_create(cursor, project, name, options, namespace_id=None):

    to_return = {
        '_id': namespace_id or uuid.uuid4().hex,
        'project_id': extract_obj_id(project),
        'name': name,
        'options': options
    }

    to_insert = (
        to_return['_id'], to_return['project_id'], name, json.dumps(options)
    )

    query = "INSERT INTO namespaces (_id, project_id, name, options) VALUES (?, ?, ?, ?)"

    try:
        cursor.execute(query, to_insert)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_return, None))


@coroutine
def namespace_edit(cursor, namespace, name, options):

    to_return = {
        '_id': extract_obj_id(namespace),
        'name': name,
        'options': options
    }

    to_update = (name, json.dumps(options), extract_obj_id(namespace))

    query = "UPDATE namespaces SET name=?, options=? WHERE _id=?"

    try:
        cursor.execute(query, to_update)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_return, None))


@coroutine
def namespace_delete(cursor, namespace):
    haystack = (extract_obj_id(namespace),)
    query = "DELETE FROM namespaces WHERE _id=?"
    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((True, None))
