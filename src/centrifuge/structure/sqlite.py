# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import sqlite3
from tornado.gen import coroutine, Return
import uuid
from bson import ObjectId
from ..log import logger


def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d


def on_error(error):
    """
    General error wrapper.
    """
    logger.error(str(error))
    raise Return((None, error))


def init_storage(structure, settings, ready_callback):
    conn = sqlite3.connect(settings.get('path', 'centrifuge.db'))
    conn.row_factory = dict_factory
    cursor = conn.cursor()

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

    cursor.execute(project, ())
    conn.commit()
    cursor.execute(category, ())
    conn.commit()

    structure.set_db(cursor)
    ready_callback()
    logger.info("Database ready")


def extract_obj_id(obj):
    if isinstance(obj, dict):
        obj_id = obj['_id']
    else:
        obj_id = obj
    return obj_id


@coroutine
def project_list(cursor):
    """
    Get all projects user can see.
    """
    query = "SELECT * FROM projects"
    try:
        cursor.execute(query, {},)
    except Exception as e:
        on_error(e)
    else:
        projects = cursor.fetchall()
        print projects
        raise Return((projects, None))


@coroutine
def project_create(
        cursor,
        name,
        display_name,
        auth_address,
        max_auth_attempts,
        back_off_interval,
        back_off_max_timeout):

    to_insert = (
        str(ObjectId()),
        name,
        display_name,
        auth_address,
        max_auth_attempts,
        back_off_interval,
        back_off_max_timeout,
        uuid.uuid4().hex
    )

    query = "INSERT INTO projects (_id, name, display_name, " \
            "auth_address, max_auth_attempts, back_off_interval, back_off_max_timeout, secret_key) " \
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)"

    try:
        cursor.execute(query, to_insert)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_insert, None))


@coroutine
def project_edit(
        cursor,
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
    to_return = {
        '_id': extract_obj_id(project),
        'name': name,
        'display_name': display_name,
        'auth_address': auth_address,
        'max_auth_attempts': max_auth_attempts,
        'back_off_interval': back_off_interval,
        'back_off_max_timeout': back_off_max_timeout
    }

    to_update = (
        name, display_name, auth_address, max_auth_attempts, back_off_interval,
        back_off_max_timeout, extract_obj_id(project)
    )

    query = "UPDATE projects SET name=?, display_name=?, auth_address=?, " \
            "max_auth_attempts=?, back_off_interval=?, back_off_max_timeout=? " \
            "WHERE _id=?"

    try:
        cursor.execute(query, to_update)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_return, None))


@coroutine
def project_delete(cursor, project):
    """
    Delete project. Also delete all related categories and events.
    """
    haystack = (project['_id'], )

    query = "DELETE FROM projects WHERE _id=?"
    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)

    query = "DELETE FROM categories WHERE project_id=?"
    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((True, None))


@coroutine
def category_list(cursor):
    """
    Get all categories
    """
    query = "SELECT * FROM categories"
    try:
        cursor.execute(query, ())
    except Exception as e:
        on_error(e)
    else:
        categories = cursor.fetchall()
        raise Return((categories, None))


@coroutine
def category_create(
        cursor,
        project,
        name,
        is_bidirectional,
        is_watching,
        presence,
        presence_ping_interval,
        presence_expire_interval,
        history,
        history_size):

    to_return = {
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

    to_insert = (
        to_return['_id'], to_return['project_id'], name, is_bidirectional,
        is_watching, presence, presence_ping_interval, presence_expire_interval,
        history, history_size
    )

    query = "INSERT INTO categories (_id, project_id, name, is_bidirectional, " \
            "is_watching, presence, presence_ping_interval, presence_expire_interval, " \
            "history, history_size) VALUES (?, ?, ?, " \
            "?, ?, ?, ?, " \
            "?, ?, ?)"

    try:
        cursor.execute(query, to_insert)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_insert, None))

@coroutine
def category_edit(
        cursor,
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
    to_return = {
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

    to_update = (
        name, is_bidirectional, is_watching, presence, presence_ping_interval,
        presence_expire_interval, history, history_size, category['_id']
    )

    query = "UPDATE categories SET name=?, is_bidirectional=?, " \
            "is_watching=?, presence=?, " \
            "presence_ping_interval=?, " \
            "presence_expire_interval=?, " \
            "history=?, history_size=? " \
            "WHERE _id=?"

    try:
        cursor.execute(query, to_update)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((to_return, None))

@coroutine
def category_delete(cursor, project, category_name):
    """
    Delete category from project. Also delete all related entries from
    event collection.
    """
    haystack = (category_name, project['_id'])
    query = "DELETE FROM categories WHERE name=? AND project_id=?"
    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((True, None))


@coroutine
def regenerate_project_secret_key(cursor, project):
    """
    Create new secret and public keys for user in specified project.
    """
    project_id = extract_obj_id(project)
    secret_key = uuid.uuid4().hex
    haystack = (secret_key, project_id)

    query = "UPDATE projects SET secret_key=? " \
            "WHERE _id=?"

    try:
        cursor.execute(query, haystack)
    except Exception as e:
        on_error(e)
    else:
        cursor.connection.commit()
        raise Return((secret_key, None))


def projects_by_id(projects):
    #import pdb; pdb.set_trace()
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