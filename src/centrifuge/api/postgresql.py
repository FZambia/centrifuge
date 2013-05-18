# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import logging
from tornado.gen import Task, coroutine, Return, engine
import momoko


def on_error(error):
    """
    General error wrapper.
    """
    logging.error(str(error))
    raise Return((None, error))


@coroutine
def on_app_started(db, drop=False):

    user = 'CREATE TABLE IF NOT EXISTS users (id integer PRIMARY KEY, ' \
           'email varchar(150) NOT NULL)'

    project = 'CREATE TABLE IF NOT EXISTS projects (id integer PRIMARY KEY, ' \
              'name varchar(100) NOT NULL, display_name varchar(100) NOT NULL, ' \
              'description text, validate_url varchar(255), auth_attempts integer, ' \
              'back_off integer)'

    project_key = 'CREATE TABLE IF NOT EXISTS project_keys (id integer PRIMARY KEY, ' \
                  'project_id integer, user_id integer, public_key varchar(32), ' \
                  'secret_key varchar(32), readonly bool)'

    category = 'CREATE TABLE IF NOT EXISTS categories (id integer PRIMARY KEY, ' \
               'project_id integer, name varchar(100), bidirectional bool, ' \
               'publish_to_admins bool)'

    logging.info("database ready")

    yield momoko.Op(db.execute, user, ())
    yield momoko.Op(db.execute, project, ())
    yield momoko.Op(db.execute, project_key, ())
    yield momoko.Op(db.execute, category, ())


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