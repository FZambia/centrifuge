# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
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


def init_db(state, settings, ready_callback):
    dsn = 'dbname=%s user=%s password=%s host=%s port=%s' % (
        settings.get('name', 'centrifuge'),
        settings.get('user', 'postgres'),
        settings.get('password', ''),
        settings.get('host', 'localhost'),
        settings.get('port', 5432)
    )
    callback = partial(on_connection_ready, state, ready_callback)
    db = momoko.Pool(
        dsn=dsn, size=settings.get('pool_size', 10), callback=callback
    )
    state.set_db(db)


@coroutine
def on_connection_ready(state, ready_callback):

    db = state.db

    project = 'CREATE TABLE IF NOT EXISTS projects (id SERIAL, _id varchar(24) UNIQUE, ' \
              'name varchar(100) NOT NULL UNIQUE, display_name ' \
              'varchar(100) NOT NULL, description text, validate_url varchar(255), ' \
              'auth_attempts integer, back_off_interval integer, ' \
              'back_off_max_timeout integer, secret_key varchar(32))'

    category = 'CREATE TABLE IF NOT EXISTS categories (id SERIAL, ' \
               '_id varchar(24) UNIQUE, project_id varchar(24), ' \
               'name varchar(100) NOT NULL UNIQUE, bidirectional bool, ' \
               'publish_to_admins bool)'

    yield momoko.Op(db.execute, project, ())
    yield momoko.Op(db.execute, category, ())
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
def project_create(db, project_name, display_name,
                   description, validate_url, auth_attempts,
                   back_off_interval, back_off_max_timeout):
    to_insert = {
        '_id': str(ObjectId()),
        'name': project_name,
        'display_name': display_name,
        'description': description,
        'validate_url': validate_url,
        'auth_attempts': auth_attempts or None,
        'back_off_interval': back_off_interval or None,
        'back_off_max_timeout': back_off_max_timeout or None,
        'secret_key': uuid.uuid4().hex
    }

    query = "INSERT INTO projects (_id, name, display_name, description, " \
            "validate_url, auth_attempts, back_off_interval, back_off_max_timeout, secret_key) " \
            "VALUES (%(_id)s, %(name)s, %(display_name)s, %(description)s, " \
            "%(validate_url)s, %(auth_attempts)s, %(back_off_interval)s, " \
            "%(back_off_max_timeout)s, %(secret_key)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))


@coroutine
def project_edit(db, project, name, display_name,
                 description, validate_url, auth_attempts,
                 back_off_interval, back_off_max_timeout):
    """
    Edit project
    """
    to_update = {
        '_id': extract_obj_id(project),
        'name': name,
        'display_name': display_name,
        'description': description,
        'validate_url': validate_url,
        'auth_attempts': auth_attempts or None,
        'back_off_interval': back_off_interval or None,
        'back_off_max_timeout': back_off_max_timeout or None
    }

    query = "UPDATE projects SET name=%(name)s, display_name=%(display_name)s, " \
            "description=%(description)s, validate_url=%(validate_url)s, " \
            "auth_attempts=%(auth_attempts)s, back_off_interval=%(back_off_interval)s, " \
            "back_off_max_timeout=%(back_off_max_timeout)s WHERE " \
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
    Delete project. Also delete all related categories and events.
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

    query = "DELETE FROM categories WHERE project_id=%(project_id)s"
    try:
        yield momoko.Op(
            db.execute, query, haystack
        )
    except Exception as e:
        on_error(e)

    raise Return((True, None))


@coroutine
def category_list(db):
    """
    Get all categories
    """
    query = "SELECT * FROM categories"
    try:
        cursor = yield momoko.Op(
            db.execute, query, {},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        categories = cursor.fetchall()
        raise Return((categories, None))


@coroutine
def category_create(db, project, category_name,
                    bidirectional=False, publish_to_admins=False):

    to_insert = {
        '_id': str(ObjectId()),
        'project_id': project['_id'],
        'name': category_name,
        'bidirectional': bidirectional,
        'publish_to_admins': publish_to_admins
    }

    query = "INSERT INTO categories (_id, project_id, name, bidirectional, " \
            "publish_to_admins) VALUES (%(_id)s, %(project_id)s, %(name)s, " \
            "%(bidirectional)s, %(publish_to_admins)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))


@coroutine
def category_delete(db, project, category_name):
    """
    Delete category from project. Also delete all related entries from
    event collection.
    """
    haystack = {
        'project_id': project['_id'],
        'name': category_name
    }

    query = "DELETE FROM categories WHERE name=%(name)s AND project_id=%(project_id)s"

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

    query = "UPDATE projects * SET secret_key=%(secret_key)s " \
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


def categories_by_id(categories):
    to_return = {}
    for category in categories:
        to_return[category['_id']] = category
    return to_return


def categories_by_name(categories):
    to_return = {}
    for category in categories:
        if category['project_id'] not in to_return:
            to_return[category['project_id']] = {}
        to_return[category['project_id']][category['name']] = category
    return to_return


def project_categories(categories):
    to_return = {}
    for category in categories:
        if category['project_id'] not in to_return:
            to_return[category['project_id']] = []
        to_return[category['project_id']].append(category)
    return to_return