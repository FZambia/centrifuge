# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import logging
from tornado.gen import coroutine, Return
import momoko
import psycopg2.extras
import uuid
from bson import ObjectId
from .. import auth
from functools import partial


def on_error(error):
    """
    General error wrapper.
    """
    logging.error(str(error))
    raise Return((None, error))


def init_db(app, settings):
    dsn = 'dbname=%s user=%s password=%s host=%s port=%s' % (
        settings.get('name', 'centrifuge'),
        settings.get('user', 'postgres'),
        settings.get('password', ''),
        settings.get('host', 'localhost'),
        settings.get('port', 5432)
    )
    callback = partial(on_connection_ready, app)
    db = momoko.Pool(
        dsn=dsn, size=settings.get('size', 10), callback=callback
    )
    app.db = db


@coroutine
def on_connection_ready(app):

    db = app.db

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
    logging.info("Database ready")


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
def get_categories_for_projects(db, projects):

    categories = []

    project_ids = [extract_obj_id(x) for x in projects]
    query = "SELECT * FROM categories WHERE project_id IN %s"
    if project_ids:
        try:
            cursor = yield momoko.Op(
                db.execute, query, (tuple(project_ids),),
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            on_error(e)
        else:
            categories = cursor.fetchall()

    to_return = {}
    for category in categories:
        if category['project_id'] not in to_return:
            to_return[category['project_id']] = []
        to_return[category['project_id']].append(category)

    raise Return((to_return, None))


@coroutine
def get_project_by_name(db, project_name):
    query = "SELECT * FROM projects WHERE name=%(name)s LIMIT 1"
    try:
        cursor = yield momoko.Op(
            db.execute, query, {'name': project_name},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        project = cursor.fetchone()
        raise Return((project, None))


@coroutine
def get_project_by_id(db, project_id):
    query = "SELECT * FROM projects WHERE _id=%(project_id)s LIMIT 1"
    try:
        cursor = yield momoko.Op(
            db.execute, query, {'project_id': project_id},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        project = cursor.fetchone()
        raise Return((project, None))


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
def get_project_categories(db, project):
    project_id = extract_obj_id(project)

    query = "SELECT * FROM categories WHERE project_id=%(project_id)s"

    try:
        cursor = yield momoko.Op(
            db.execute, query, {'project_id': project_id},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        categories = cursor.fetchall()
        raise Return((categories, None))


@coroutine
def get_project_users(db, project):

    query = "SELECT t1._id, t1.email, t2.is_active, t2.public_key, t2.secret_key, t2.readonly " \
            "FROM users t1 JOIN project_keys t2 on t1._id=t2.user_id WHERE " \
            "project_id=%(project_id)s AND is_active=%(is_active)s"

    try:
        cursor = yield momoko.Op(
            db.execute, query, {'project_id': extract_obj_id(project), 'is_active': True},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        users = cursor.fetchall()
        raise Return((users, None))


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


@coroutine
def get_project_category(db, project, category_name):
    """
    Find category by name for project.
    """
    haystack = {
        'project_id': project['_id'],
        'name': category_name
    }

    query = "SELECT * FROM categories WHERE name=%(name)s AND " \
            "project_id=%(project_id)s LIMIT 1"

    try:
        cursor = yield momoko.Op(
            db.execute, query, haystack,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        category = cursor.fetchone()
        raise Return((category, None))


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
    category, error = yield get_project_category(db, project, category_name)

    if not category:
        raise Return((True, None))

    haystack = {
        'project_id': project['_id'],
        '_id': category['_id']
    }

    query = "DELETE FROM categories WHERE _id=%(_id)s AND project_id=%(project_id)s"

    try:
        yield momoko.Op(
            db.execute, query, haystack
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((True, None))


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
