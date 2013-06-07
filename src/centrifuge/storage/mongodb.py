# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import uuid
import time
import logging
import motor
from bson import ObjectId
from tornado.gen import Task, coroutine, Return
from .. import auth


def on_error(error):
    """
    General error wrapper.
    """
    logging.error(str(error))
    raise Return((None, error))


def ensure_indexes(db, drop=False):
    if drop:
        logging.info('dropping indexes...')
        db.project.drop_indexes()
        db.category.drop_indexes()

    db.project.ensure_index([('name', 1)], unique=True)
    db.category.ensure_index([('name', 1), ('project', 1)], unique=True)

    logging.info('Database ready')


def init_db(app, settings):
    """
    Create MongoDB connection, ensure indexes
    """
    db = motor.MotorClient(
        host=settings.get("host", "localhost"),
        port=settings.get("port", 27017),
        max_pool_size=settings.get("max_pool_size", 10)
    ).open_sync()[settings.get("name", "centrifuge")]

    app.db = db

    ensure_indexes(db)


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
    if 'is_active' not in data:
        data['is_active'] = True
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
def find_one_or_create(collection, haystack):
    """
    First try to find object by haystack, create new if not found.
    """
    obj, error = yield find_one(collection, haystack)
    if error:
        on_error(error)

    if not obj:
        obj_id = str(ObjectId())
        haystack['_id'] = obj_id
        result, error = yield insert(collection, haystack)
        if error:
            on_error(error)
        obj = haystack

    raise Return((obj, None))


@coroutine
def check_auth(db, project, sign, encoded_data):
    """
    Authenticate incoming request. Make sure that it has all rights
    to create new events in specified project.
    """
    assert isinstance(project, dict)

    is_authenticated = auth.check_sign(
        project['secret_key'],
        project['_id'],
        encoded_data,
        sign
    )
    if not is_authenticated:
        raise Return((None, None))

    raise Return((True, None))


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
def get_project_by_name(db, project_name):
    project, error = yield find_one(db.project, {'name': project_name})
    if error:
        on_error(error)
    raise Return((project, None))


@coroutine
def get_project_by_id(db, project_id):
    project, error = yield find_one(db.project, {'_id': project_id})
    if error:
        on_error(error)
        return
    raise Return((project, None))


@coroutine
def get_project_categories(db, project):
    project_id = extract_obj_id(project)
    categories, error = yield find(db.category, {'project': project_id})
    if error:
        on_error(error)
        return
    raise Return((categories, None))


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
    category, error = yield get_project_category(db, project, category_name)

    if not category:
        raise Return((True, None))

    haystack = {
        'project': project['_id'],
        '_id': category['_id']
    }
    _res, error = yield remove(db.category, haystack)
    if error:
        on_error(error)

    raise Return((True, None))


@coroutine
def get_project_category(db, project, category_name):
    """
    Find category by name for project.
    """
    haystack = {
        'project': project['_id'],
        'name': category_name
    }
    category, error = yield find_one(db.category, haystack)
    if error:
        on_error(error)

    raise Return((category, None))


@coroutine
def get_categories_for_projects(db, projects):
    """
    pass
    """
    project_ids = [extract_obj_id(x) for x in projects]
    haystack = {
        "project": {"$in": project_ids}
    }

    categories, error = yield find(db.category, haystack)
    if error:
        on_error(error)

    to_return = {}

    for category in categories:
        if category['project'] not in to_return:
            to_return[category['project']] = []
        to_return[category['project']].append(category)

    raise Return((to_return, None))
