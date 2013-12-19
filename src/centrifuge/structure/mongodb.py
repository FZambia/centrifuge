# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import uuid
import motor
from tornado.gen import Task, coroutine, Return

from centrifuge.log import logger


NAME = "MongoDB"


def on_error(error):
    logger.error(str(error))
    raise Return((None, error))


def ensure_indexes(db, drop=False):
    if drop:
        logger.info('dropping indexes...')
        db.project.drop_indexes()
        db.namespace.drop_indexes()

    db.namespace.ensure_index([('name', 1), ('project_id', 1)], unique=True)

    logger.info('Database ready')


def init_storage(structure, settings, callback):
    """
    Create MongoDB connection, ensure indexes
    """
    db = motor.MotorClient(
        host=settings.get("host", "localhost"),
        port=settings.get("port", 27017),
        max_pool_size=settings.get("pool_size", 10)
    ).open_sync()[settings.get("name", "centrifuge")]

    structure.set_db(db)

    ensure_indexes(db)

    callback()


def extract_obj_id(obj):
    return obj['_id']


@coroutine
def insert(collection, data):
    """
    Insert data into collection.
    """
    (result, error), _ = yield Task(collection.insert, data)
    if error:
        on_error(error)

    raise Return((result, None))


@coroutine
def find(collection, haystack):
    """
    Find objects in MongoDB collection by haystack.
    """
    cursor = collection.find(haystack, limit=10000)
    (objects, error), _ = yield Task(cursor.to_list)
    if error:
        on_error(error)

    raise Return((objects, None))


@coroutine
def update(collection, haystack, update_data):
    """
    Update entries matching haystack with update_data.
    """
    (result, error), _ = yield Task(
        collection.update, haystack, {"$set": update_data}
    )
    if error:
        on_error(error)
    raise Return((result, None))


@coroutine
def find_one(collection, haystack):
    """
    Find object in MongoDB collection.
    """
    (obj, error), _ = yield Task(collection.find_one, haystack)
    if error:
        on_error(error)
    if not obj:
        raise Return((None, None))
    raise Return((obj, None))


@coroutine
def remove(collection, haystack):
    """
    Find object in MongoDB collection.
    """
    (res, error), _ = yield Task(collection.remove, haystack)
    if error:
        on_error(error)

    raise Return((res, None))


@coroutine
def project_list(db):

    projects, error = yield find(db.project, {})
    if error:
        on_error(error)

    raise Return((projects, None))


@coroutine
def project_create(db, options):

    to_insert = {
        '_id': uuid.uuid4().hex,
        'secret_key': uuid.uuid4().hex,
        'options': options
    }
    result, error = yield insert(db.project, to_insert)
    if error:
        on_error(error)
        return
    raise Return((to_insert, None))


@coroutine
def project_edit(db, project, options):

    to_update = {
        'options': options
    }
    _res, error = yield update(
        db.project,
        {'_id': extract_obj_id(project)},
        to_update
    )
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def regenerate_project_secret_key(db, project, secret_key):

    haystack = {
        '_id': extract_obj_id(project)
    }
    update_data = {
        'secret_key': secret_key
    }
    result, error = yield update(db.project, haystack, update_data)
    if error:
        on_error(error)

    raise Return((update_data, None))


@coroutine
def project_delete(db, project):
    """
    Delete project. Also delete all related namespaces.
    """
    haystack = {
        '_id': extract_obj_id(project)
    }
    _res, error = yield remove(db.project, haystack)
    if error:
        on_error(error)

    haystack = {
        'project_id': extract_obj_id(project)
    }
    _res, error = yield remove(db.namespace, haystack)
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def namespace_list(db):

    namespaces, error = yield find(db.namespace, {})
    if error:
        on_error(error)

    raise Return((namespaces, None))


@coroutine
def namespace_create(db, project, name, options):

    haystack = {
        '_id': uuid.uuid4().hex,
        'project_id': extract_obj_id(project),
        'name': name,
        'options': options
    }
    namespace, error = yield insert(db.namespace, haystack)
    if error:
        on_error(error)

    raise Return((namespace, None))


@coroutine
def namespace_edit(db, namespace, name, options):

    to_update = {
        'name': name,
        'options': options
    }
    _res, error = yield update(
        db.namespace,
        {'_id': extract_obj_id(namespace)},
        to_update
    )
    if error:
        on_error(error)

    raise Return((namespace, None))


@coroutine
def namespace_delete(db, namespace):

    haystack = {
        '_id': extract_obj_id(namespace)
    }
    _res, error = yield remove(db.namespace, haystack)
    if error:
        on_error(error)

    raise Return((True, None))
