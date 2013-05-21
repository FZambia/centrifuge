# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import logging
from tornado.gen import Task, coroutine, Return, engine
import momoko
import psycopg2.extras
import uuid
from bson import ObjectId


def on_error(error):
    """
    General error wrapper.
    """
    logging.error(str(error))
    raise Return((None, error))


@coroutine
def on_app_started(db, drop=False):

    user = 'CREATE TABLE IF NOT EXISTS users (id SERIAL, ' \
           '_id varchar(24), email varchar(150) NOT NULL)'

    project = 'CREATE TABLE IF NOT EXISTS projects (id SERIAL, _id varchar(24), ' \
              'owner varchar(24), name varchar(100) NOT NULL, display_name ' \
              'varchar(100) NOT NULL, description text, validate_url varchar(255), ' \
              'auth_attempts integer, back_off_interval integer, ' \
              'back_off_max_timeout integer)'

    project_key = 'CREATE TABLE IF NOT EXISTS project_keys (id SERIAL, ' \
                  '_id varchar(24), project_id varchar(24), user_id varchar(24), ' \
                  'public_key varchar(32), secret_key varchar(32), readonly bool)'

    category = 'CREATE TABLE IF NOT EXISTS categories (id SERIAL, ' \
               '_id varchar(24), project_id varchar(24), name varchar(100), ' \
               'bidirectional bool, publish_to_admins bool)'

    yield momoko.Op(db.execute, user, ())
    yield momoko.Op(db.execute, project, ())
    yield momoko.Op(db.execute, project_key, ())
    yield momoko.Op(db.execute, category, ())
    logging.info("database ready")


def get_db(settings):
    """
    Create connection, ensure indexes
    """
    dsn = 'dbname=%s user=%s password=%s host=%s port=%s' % (
        settings.get('name', 'centrifuge'),
        settings.get('user', 'postgres'),
        settings.get('password', ''),
        settings.get('host', 'localhost'),
        settings.get('port', 5432)
    )
    db = momoko.Pool(dsn=dsn, size=10)
    return db


def extract_obj_id(obj):
    if isinstance(obj, dict):
        obj_id = obj['_id']
    else:
        obj_id = obj
    return obj_id


@coroutine
def get_or_create_user(db, email):
    """
    Get user by email and return it's data if user exists.
    Otherwise create new user using provided arguments.
    """
    query = "SELECT * FROM users WHERE email=%(email)s LIMIT 1"
    cursor = yield momoko.Op(
        db.execute, query, {'email': email},
        cursor_factory=psycopg2.extras.RealDictCursor
    )
    user_data = cursor.fetchone()

    if not user_data:
        user_data = {
            '_id': str(ObjectId()),
            'email': email
        }
        query = "INSERT INTO users (_id, email) VALUES (%(_id)s, %(email)s)"
        try:
            yield momoko.Op(
                db.execute, query, user_data,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            on_error(e)

    raise Return((user_data, None))


@coroutine
def get_user_projects(db, user):
    """
    Get all projects user can see.
    """
    query = "SELECT * FROM projects WHERE _id IN (SELECT project_id FROM " \
            "project_keys WHERE user_id=%(user_id)s)"
    try:
        cursor = yield momoko.Op(
            db.execute, query, {'user_id': user['_id']},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        projects = cursor.fetchall()
        raise Return((projects, None))


@coroutine
def get_categories_for_projects(db, projects):

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
    else:
        categories = []

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
def project_create(db, user, project_name, display_name,
                   description, validate_url, auth_attempts,
                   back_off_interval, back_off_max_timeout):
    user_id = extract_obj_id(user)
    to_insert = {
        '_id': str(ObjectId()),
        'owner': user_id,
        'name': project_name,
        'display_name': display_name,
        'description': description,
        'validate_url': validate_url,
        'auth_attempts': auth_attempts or None,
        'back_off_interval': back_off_interval or None,
        'back_off_max_timeout': back_off_max_timeout or None
    }

    query = "INSERT INTO projects (_id, owner, name, display_name, description, " \
            "validate_url, auth_attempts, back_off_interval, back_off_max_timeout) " \
            "VALUES (%(_id)s, %(owner)s, %(name)s, %(display_name)s, %(description)s, " \
            "%(validate_url)s, %(auth_attempts)s, %(back_off_interval)s, " \
            "%(back_off_max_timeout)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))


@coroutine
def add_user_into_project(db, user, project, readonly):

    user_id = extract_obj_id(user)
    project_id = extract_obj_id(project)

    haystack = {
        'project_id': project_id,
        'user_id': user_id
    }

    query = "SELECT * FROM project_keys WHERE user_id=%(user_id)s AND " \
            "project_id=%(project_id)s LIMIT 1"

    try:
        cursor = yield momoko.Op(
            db.execute, query, haystack,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        project_key = cursor.fetchone()

        if not project_key:
            project_key, error = yield generate_project_keys(
                db, user_id, project_id, readonly
            )
            if error:
                on_error(error)

        elif not project_key.get('is_active', False):
            to_update = {
                'is_active': True,
                'readonly': readonly
            }
            to_update.update(haystack)

            query = "UPDATE TABLE project_keys SET is_active=%(is_active), " \
                    "readonly=%(readonly)s WHERE user_id=%(user_id)s AND " \
                    "project_id=%(project_id)s"

            try:
                yield momoko.Op(
                    db.execute, query, to_update
                )
            except Exception as e:
                on_error(e)

        raise Return((project_key, None))


@coroutine
def generate_project_keys(db, user_id, project_id, readonly):
    """
    Create secret and public keys for user in specified project.
    """
    to_insert = {
        '_id': str(ObjectId()),
        'project_id': project_id,
        'user_id': user_id,
        'public_key': uuid.uuid4().hex,
        'secret_key': uuid.uuid4().hex,
        'readonly': readonly
    }

    query = "INSERT INTO project_keys (_id, project_id, user_id, public_key, " \
            "secret_key, readonly) VALUES (%(_id)s, %(project_id)s, %(user_id)s, " \
            "%(public_key)s, %(secret_key)s, %(readonly)s)"

    try:
        yield momoko.Op(
            db.execute, query, to_insert,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        raise Return((to_insert, None))


@coroutine
def get_user_project_key(db, user, project):
    user_id = extract_obj_id(user)
    project_id = extract_obj_id(project)
    haystack = {
        'project_id': project_id,
        'user_id': user_id
    }

    query = "SELECT * FROM project_keys WHERE project_id=%(project_id)s AND " \
            "user_id=%(user_id)s"

    try:
        cursor = yield momoko.Op(
            db.execute, query, haystack,
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        project_key = cursor.fetchone()
        raise Return((project_key, None))


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

    query = "SELECT t1._id, t1.email, t2.public_key, t2.secret_key, t2.readonly " \
            "FROM users t1 JOIN project_keys t2 on t1._id=t2.user_id WHERE " \
            "project_id=%(project_id)s"

    try:
        cursor = yield momoko.Op(
            db.execute, query, {'project_id': extract_obj_id(project)},
            cursor_factory=psycopg2.extras.RealDictCursor
        )
    except Exception as e:
        on_error(e)
    else:
        users = cursor.fetchall()
        raise Return((users, None))
