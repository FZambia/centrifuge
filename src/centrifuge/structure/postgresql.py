# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.gen import coroutine, Return
import momoko
import psycopg2.extras
import uuid
from bson import ObjectId
from functools import partial
from ..log import logger


def on_error(error):
    """
    General error wrapper.
    """
    logger.error(str(error))
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

    project = 'CREATE TABLE IF NOT EXISTS projects (id SERIAL, _id varchar(24) UNIQUE, ' \
              'name varchar(100) NOT NULL UNIQUE, display_name ' \
              'varchar(100) NOT NULL, auth_address varchar(255), ' \
              'max_auth_attempts integer, back_off_interval integer, ' \
              'back_off_max_timeout integer, secret_key varchar(32), ' \
              'default_namespace varchar(32))'

    namespace = 'CREATE TABLE IF NOT EXISTS namespaces (id SERIAL, ' \
               '_id varchar(24) UNIQUE, project_id varchar(24), ' \
               'name varchar(100) NOT NULL UNIQUE, publish bool, ' \
               'is_watching bool, presence bool, history bool, history_size integer, ' \
               'is_private bool, auth_address varchar(255))'

    yield momoko.Op(db.execute, project, ())
    yield momoko.Op(db.execute, namespace, ())
    ready_callback()
    logger.info("Database ready")


def extract_obj_id(obj):
    if isinstance(obj, dict):
        obj_id = obj['_id']
    else:
        obj_id = obj
    return obj_id


@coroutine
def project_list(db):
    """
    Get all projects user can see.
    """
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
def project_create(db, **kwargs):

    to_insert = {
        '_id': str(ObjectId()),
        'name': kwargs['name'],
        'display_name': kwargs['display_name'],
        'auth_address': kwargs['auth_address'],
        'max_auth_attempts': kwargs['max_auth_attempts'],
        'back_off_interval': kwargs['back_off_interval'],
        'back_off_max_timeout': kwargs['back_off_max_timeout'],
        'secret_key': uuid.uuid4().hex,
        'default_namespace': None
    }

    query = "INSERT INTO projects (_id, name, display_name, " \
            "auth_address, max_auth_attempts, back_off_interval, back_off_max_timeout, secret_key, default_namespace) " \
            "VALUES (%(_id)s, %(name)s, %(display_name)s, " \
            "%(auth_address)s, %(max_auth_attempts)s, %(back_off_interval)s, " \
            "%(back_off_max_timeout)s, %(secret_key)s, %(default_namespace)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))


@coroutine
def project_edit(db, project, **kwargs):
    """
    Edit project
    """
    to_update = {
        '_id': extract_obj_id(project),
        'name': kwargs['name'],
        'display_name': kwargs['display_name'],
        'auth_address': kwargs['auth_address'],
        'max_auth_attempts': kwargs['max_auth_attempts'],
        'back_off_interval': kwargs['back_off_interval'],
        'back_off_max_timeout': kwargs['back_off_max_timeout'],
        'default_namespace': kwargs['default_namespace']
    }

    query = "UPDATE projects SET name=%(name)s, display_name=%(display_name)s, " \
            "auth_address=%(auth_address)s, " \
            "max_auth_attempts=%(max_auth_attempts)s, back_off_interval=%(back_off_interval)s, " \
            "back_off_max_timeout=%(back_off_max_timeout)s, default_namespace=%(default_namespace)s WHERE " \
            "_id=%(_id)s"

    try:
        yield momoko.Op(
            db.execute, query, to_update
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_update, None))


@coroutine
def project_delete(db, project):
    """
    Delete project. Also delete all related namespaces and events.
    """
    haystack = {
        'project_id': project['_id']
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
    """
    Get all namespaces
    """
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
def namespace_create(db, project, **kwargs):

    to_insert = {
        '_id': str(ObjectId()),
        'project_id': project['_id'],
        'name': kwargs['name'],
        'publish': kwargs['publish'],
        'is_watching': kwargs['is_watching'],
        'presence': kwargs['presence'],
        'history': kwargs['history'],
        'history_size': kwargs['history_size'],
        'is_private': kwargs['is_private'],
        'auth_address': kwargs['auth_address']
    }

    query = "INSERT INTO namespaces (_id, project_id, name, publish, " \
            "is_watching, presence, history, history_size, is_private, " \
            "auth_address) VALUES (%(_id)s, %(project_id)s, %(name)s, " \
            "%(publish)s, %(is_watching)s, %(presence)s, " \
            "%(history)s, %(history_size)s, %(is_private)s, %(auth_address)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))


@coroutine
def namespace_edit(db, namespace, **kwargs):
    """
    Edit project
    """
    to_update = {
        '_id': namespace['_id'],
        'name': kwargs['name'],
        'publish': kwargs['publish'],
        'is_watching': kwargs['is_watching'],
        'presence': kwargs['presence'],
        'history': kwargs['history'],
        'history_size': kwargs['history_size'],
        'is_private': kwargs['is_private'],
        'auth_address': kwargs['auth_address']
    }

    query = "UPDATE namespaces SET name=%(name)s, publish=%(publish)s, " \
            "is_watching=%(is_watching)s, presence=%(presence)s, " \
            "history=%(history)s, history_size=%(history_size)s, " \
            "is_private=%(is_private)s, auth_address=%(auth_address)s " \
            "WHERE _id=%(_id)s"

    try:
        yield momoko.Op(
            db.execute, query, to_update
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_update, None))


@coroutine
def namespace_delete(db, project, namespace_name):
    """
    Delete namespace from project. Also delete all related entries from
    event collection.
    """
    haystack = {
        'project_id': project['_id'],
        'name': namespace_name
    }

    query = "DELETE FROM namespaces WHERE name=%(name)s AND project_id=%(project_id)s"

    try:
        yield momoko.Op(
            db.execute, query, haystack
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((True, None))


@coroutine
def regenerate_project_secret_key(db, project):
    """
    Create new secret and public keys for user in specified project.
    """
    project_id = extract_obj_id(project)
    secret_key = uuid.uuid4().hex
    haystack = {
        'project_id': project_id,
        'secret_key': secret_key
    }

    query = "UPDATE projects SET secret_key=%(secret_key)s " \
            "WHERE _id=%(project_id)s"

    try:
        yield momoko.Op(
            db.execute, query, haystack,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
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