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
              'back_off_max_timeout integer, secret_key varchar(32))'

    category = 'CREATE TABLE IF NOT EXISTS categories (id SERIAL, ' \
               '_id varchar(24) UNIQUE, project_id varchar(24), ' \
               'name varchar(100) NOT NULL UNIQUE, is_bidirectional bool, ' \
               'is_watching bool, presence bool, presence_ping_interval integer, ' \
               'presence_expire_interval integer, history bool, history_size integer)'

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
def project_create(
        db,
        name,
        display_name,
        auth_address,
        max_auth_attempts,
        back_off_interval,
        back_off_max_timeout):

    to_insert = {
        '_id': str(ObjectId()),
        'name': name,
        'display_name': display_name,
        'auth_address': auth_address,
        'max_auth_attempts': max_auth_attempts,
        'back_off_interval': back_off_interval,
        'back_off_max_timeout': back_off_max_timeout,
        'secret_key': uuid.uuid4().hex
    }

    query = "INSERT INTO projects (_id, name, display_name, " \
            "auth_address, max_auth_attempts, back_off_interval, back_off_max_timeout, secret_key) " \
            "VALUES (%(_id)s, %(name)s, %(display_name)s, " \
            "%(auth_address)s, %(max_auth_attempts)s, %(back_off_interval)s, " \
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
def project_edit(
        db,
        project,
        name,
        display_name,
        auth_address,
        max_auth_attempts,
        back_off_interval,
        back_off_max_timeout):
    """
    Edit project
    """
    to_update = {
        '_id': extract_obj_id(project),
        'name': name,
        'display_name': display_name,
        'auth_address': auth_address,
        'max_auth_attempts': max_auth_attempts,
        'back_off_interval': back_off_interval,
        'back_off_max_timeout': back_off_max_timeout
    }

    query = "UPDATE projects SET name=%(name)s, display_name=%(display_name)s, " \
            "auth_address=%(auth_address)s, " \
            "max_auth_attempts=%(max_auth_attempts)s, back_off_interval=%(back_off_interval)s, " \
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
def category_create(
        db,
        project,
        name,
        is_bidirectional,
        is_watching,
        presence,
        presence_ping_interval,
        presence_expire_interval,
        history,
        history_size):

    to_insert = {
        '_id': str(ObjectId()),
        'project_id': project['_id'],
        'name': name,
        'is_bidirectional': is_bidirectional,
        'is_watching': is_watching,
        'presence': presence,
        'presence_ping_interval': presence_ping_interval,
        'presence_expire_interval': presence_expire_interval,
        'history': history,
        'history_size': history_size
    }

    query = "INSERT INTO categories (_id, project_id, name, is_bidirectional, " \
            "is_watching, presense, presence_ping_interval, presence_expire_interval, " \
            "history, history_size) VALUES (%(_id)s, %(project_id)s, %(name)s, " \
            "%(is_bidirectional)s, %(is_watching)s, %(presence)s, %(presence_ping_interval)s, " \
            "%(presence_expire_interval)s, %(history)s, %(history_size)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))

@coroutine
def category_edit(
        db,
        category,
        name,
        is_bidirectional,
        is_watching,
        presence,
        presence_ping_interval,
        presence_expire_interval,
        history,
        history_size):
    """
    Edit project
    """
    to_update = {
        '_id': category['_id'],
        'name': name,
        'is_bidirectional': is_bidirectional,
        'is_watching': is_watching,
        'presence': presence,
        'presence_ping_interval': presence_ping_interval,
        'presence_expire_interval': presence_expire_interval,
        'history': history,
        'history_size': history_size
    }

    query = "UPDATE categories SET name=%(name)s, is_bidirectional=%(is_bidirectional)s, " \
            "is_watching=%(is_watching)s, presence=%(presence)s, " \
            "presence_ping_interval=%(presence_ping_interval)s, " \
            "presence_expire_interval=%(presence_expire_interval)s, " \
            "history=%(history)s, history_size=%(history_size)s " \
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