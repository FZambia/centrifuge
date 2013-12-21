# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.gen import coroutine, Return
import momoko
import psycopg2.extras
import uuid
from functools import partial
import json


NAME = "PostgreSQL"


def on_error(error):
    """
    General error wrapper.
    """
    raise Return((None, error))


def init_storage(structure, settings, ready_callback):
    dsn = 'dbname=%s user=%s password=%s host=%s port=%s' % (
        settings.get('name', 'centrifuge'),
        settings.get('user', 'postgres'),
        settings.get('password', ''),
        settings.get('host', 'localhost'),
        settings.get('port', 5432)
    )
    callback = partial(on_connection_ready, structure, ready_callback)
    db = momoko.Pool(
        dsn=dsn, size=settings.get('pool_size', 10), callback=callback
    )
    structure.set_db(db)


@coroutine
def on_connection_ready(structure, ready_callback):

    db = structure.db

    project = 'CREATE TABLE IF NOT EXISTS projects (id SERIAL, _id varchar(32) UNIQUE, ' \
              'secret_key varchar(32), options text)'

    namespace = 'CREATE TABLE IF NOT EXISTS namespaces (id SERIAL, ' \
                '_id varchar(32) UNIQUE, project_id varchar(32), ' \
                'name varchar(100) NOT NULL, options text, ' \
                'constraint namespaces_unique unique(project_id, name))'

    yield momoko.Op(db.execute, project, ())
    yield momoko.Op(db.execute, namespace, ())
    ready_callback()


def extract_obj_id(obj):
    return obj['_id']


@coroutine
def project_list(db):

    query = "SELECT * FROM projects"
    try:
        cursor = yield momoko.Op(
            db.execute, query, {},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        projects = cursor.fetchall()
        raise Return((projects, None))


@coroutine
def project_create(db, secret_key, options):

    to_insert = {
        '_id': uuid.uuid4().hex,
        'secret_key': secret_key,
        'options': json.dumps(options)
    }

    query = "INSERT INTO projects (_id, secret_key, options) VALUES (%(_id)s, %(secret_key)s, %(options)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))


@coroutine
def project_edit(db, project, options):

    to_update = {
        '_id': extract_obj_id(project),
        'options': json.dumps(options)
    }

    query = "UPDATE projects SET options=%(options)s WHERE _id=%(_id)s"

    try:
        yield momoko.Op(
            db.execute, query, to_update
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_update, None))


@coroutine
def regenerate_project_secret_key(db, project, secret_key):

    haystack = {
        '_id': extract_obj_id(project),
        'secret_key': secret_key
    }

    query = "UPDATE projects SET secret_key=%(secret_key)s WHERE _id=%(_id)s"

    try:
        yield momoko.Op(
            db.execute, query, haystack,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((secret_key, None))


@coroutine
def project_delete(db, project):
    """
    Delete project. Also delete all related namespaces.
    """
    haystack = {
        'project_id': extract_obj_id(project)
    }

    query = "DELETE FROM projects WHERE _id=%(project_id)s"
    try:
        yield momoko.Op(
            db.execute, query, haystack
        )
    except Exception as e:
        on_error(e)

    query = "DELETE FROM namespaces WHERE project_id=%(project_id)s"
    try:
        yield momoko.Op(
            db.execute, query, haystack
        )
    except Exception as e:
        on_error(e)

    raise Return((True, None))


@coroutine
def namespace_list(db):

    query = "SELECT * FROM namespaces"
    try:
        cursor = yield momoko.Op(
            db.execute, query, {},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        namespaces = cursor.fetchall()
        raise Return((namespaces, None))


@coroutine
def namespace_create(db, project, name, options):

    to_insert = {
        '_id': uuid.uuid4().hex,
        'project_id': extract_obj_id(project),
        'name': name,
        'options': json.dumps(options)
    }

    query = "INSERT INTO namespaces (_id, project_id, name, options) " \
            "VALUES (%(_id)s, %(project_id)s, %(name)s, %(options)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))


@coroutine
def namespace_edit(db, namespace, name, options):

    to_update = {
        '_id': namespace['_id'],
        'name': name,
        'options': json.dumps(options)
    }

    query = "UPDATE namespaces SET name=%(name)s, options=%(options)s WHERE _id=%(_id)s"

    try:
        yield momoko.Op(
            db.execute, query, to_update
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_update, None))


@coroutine
def namespace_delete(db, namespace):
    haystack = {
        '_id': extract_obj_id(namespace)
    }

    query = "DELETE FROM namespaces WHERE _id=%(_id)s"

    try:
        yield momoko.Op(
            db.execute, query, haystack
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((True, None))
