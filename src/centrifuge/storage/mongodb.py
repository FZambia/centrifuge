# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import uuid
import time
import motor
from bson import ObjectId
from tornado.gen import Task, coroutine, Return
from ..log import logger


def on_error(error):
    """
    General error wrapper.
    """
    logger.error(str(error))
    raise Return((None, error))


def ensure_indexes(db, drop=False):
    if drop:
        logger.info('dropping indexes...')
        db.project.drop_indexes()
        db.category.drop_indexes()

    db.project.ensure_index([('name', 1)], unique=True)
    db.category.ensure_index([('name', 1), ('project', 1)], unique=True)

    logger.info('Database ready')


def init_db(state, settings, callback):
    """
    Create MongoDB connection, ensure indexes
    """
    db = motor.MotorClient(
        host=settings.get("host", "localhost"),
        port=settings.get("port", 27017),
        max_pool_size=settings.get("pool_size", 10)
    ).open_sync()[settings.get("name", "centrifuge")]

    state.set_db(db)

    ensure_indexes(db)

    callback()


def extract_obj_id(obj):
    if isinstance(obj, dict):
        obj_id = obj['_id']
    else:
        obj_id = obj
    return obj_id


@coroutine
def insert(collection, data):
    """
    Insert data into collection.
    """
    if 'created_at' not in data:
        data['created_at'] = int(time.time())
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
    if 'updated_at' not in update_data:
        update_data['updated_at'] = int(time.time())
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
    """
    Get all projects
    """
    projects, error = yield find(db.project, {})
    if error:
        on_error(error)

    raise Return((projects, None))


@coroutine
def project_create(db, project_name, display_name,
                   description, validate_url, auth_attempts,
                   back_off_interval, back_off_max_timeout):
    project_id = str(ObjectId())
    to_insert = {
        '_id': project_id,
        'name': project_name,
        'display_name': display_name,
        'description': description,
        'validate_url': validate_url,
        'auth_attempts': auth_attempts,
        'back_off_interval': back_off_interval,
        'back_off_max_timeout': back_off_max_timeout,
        'secret_key': uuid.uuid4().hex
    }
    result, error = yield insert(db.project, to_insert)
    if error:
        on_error(error)
        return
    raise Return((to_insert, None))


@coroutine
def project_edit(db, project, name, display_name,
                 description, validate_url, auth_attempts,
                 back_off_interval, back_off_max_timeout):
    """
    Edit project
    """
    to_update = {
        'name': name,
        'display_name': display_name,
        'description': description,
        'validate_url': validate_url,
        'auth_attempts': auth_attempts,
        'back_off_interval': back_off_interval,
        'back_off_max_timeout': back_off_max_timeout
    }
    _res, error = yield update(
        db.project,
        {'_id': project['_id']},
        to_update
    )
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def project_delete(db, project):
    """
    Delete project. Also delete all related categories and events.
    """
    haystack = {
        '_id': project['_id']
    }
    _res, error = yield remove(db.project, haystack)
    if error:
        on_error(error)

    haystack = {
        'project': project['_id']
    }
    _res, error = yield remove(db.category, haystack)
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def category_list(db):
    """
    Get all categories
    """
    categories, error = yield find(db.category, {})
    if error:
        on_error(error)

    raise Return((categories, None))


@coroutine
def category_create(db, project, category_name,
                    bidirectional=False, publish_to_admins=False):

    haystack = {
        '_id': str(ObjectId()),
        'project': project['_id'],
        'name': category_name,
        'bidirectional': bidirectional,
        'publish_to_admins': publish_to_admins
    }
    category, error = yield insert(db.category, haystack)
    if error:
        on_error(error)

    raise Return((category, None))


@coroutine
def category_delete(db, project, category_name):
    """
    Delete category from project. Also delete all related entries from
    event collection.
    """
    haystack = {
        'project': project['_id'],
        'name': category_name
    }
    _res, error = yield remove(db.category, haystack)
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def regenerate_project_secret_key(db, project):
    """
    Create new secret key for specified project.
    """
    project_id = extract_obj_id(project)
    haystack = {
        '_id': project_id
    }
    update_data = {
        'secret_key': uuid.uuid4().hex
    }
    result, error = yield update(db.project, haystack, update_data)
    if error:
        on_error(error)

    raise Return((update_data, None))


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


def categories_by_id(categories):
    to_return = {}
    for category in categories:
        to_return[category['_id']] = category
    return to_return


def categories_by_name(categories):
    to_return = {}
    for category in categories:
        if category['project'] not in to_return:
            to_return[category['project']] = {}
        to_return[category['project']][category['name']] = category
    return to_return


def project_categories(categories):
    to_return = {}
    for category in categories:
        if category['project'] not in to_return:
            to_return[category['project']] = []
        to_return[category['project']].append(category)
    return to_return