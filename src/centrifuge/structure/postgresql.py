# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.gen import coroutine, Return
import momoko
import psycopg2.extras
import uuid
from functools import partial
import json

from centrifuge.structure import BaseStorage
from centrifuge.log import logger


def extract_obj_id(obj):
    return obj['_id']


def on_error(error):
    raise Return((None, error))


class PostgreSQLStorage(BaseStorage):

    NAME = "PostgreSQL"

    def __init__(self, *args, **kwargs):
        super(PostgreSQLStorage, self).__init__(*args, **kwargs)
        self._pool = None

    def create_connection_pool(self, callback=None):
        dsn = 'dbname=%s user=%s password=%s host=%s port=%s' % (
            self.settings.get('name', 'centrifuge'),
            self.settings.get('user', 'postgres'),
            self.settings.get('password', ''),
            self.settings.get('host', 'localhost'),
            self.settings.get('port', 5432)
        )

        self._pool = momoko.Pool(
            dsn=dsn, size=self.settings.get('pool_size', 10), callback=callback
        )

    def create_connection(self, callback=None):
        self.create_connection_pool(callback=partial(self.on_connection_ready, callback))

    @coroutine
    def on_connection_ready(self, ready_callback):

        project = 'CREATE TABLE IF NOT EXISTS projects (id SERIAL, _id varchar(32) UNIQUE, ' \
                  'secret_key varchar(32), options text)'

        namespace = 'CREATE TABLE IF NOT EXISTS namespaces (id SERIAL, ' \
                    '_id varchar(32) UNIQUE, project_id varchar(32), ' \
                    'name varchar(100) NOT NULL, options text, ' \
                    'constraint namespaces_unique unique(project_id, name))'

        try:
            yield momoko.Op(self._pool.execute, project, ())
            yield momoko.Op(self._pool.execute, namespace, ())
        except Exception as err:
            logger.exception(err)
        ready_callback()

    @coroutine
    def clear_structure(self):
        project = "DELETE FROM projects"
        namespace = "DELETE FROM namespaces"
        try:
            yield momoko.Op(self._pool.execute, project, ())
            yield momoko.Op(self._pool.execute, namespace, ())
        except Exception as err:
            raise Return((None, err))
        raise Return((True, None))

    @coroutine
    def project_list(self):

        query = "SELECT * FROM projects"
        try:
            cursor = yield momoko.Op(
                self._pool.execute, query, {},
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            on_error(e)
        else:
            projects = cursor.fetchall()
            raise Return((projects, None))

    @coroutine
    def project_create(self, secret_key, options, project_id=None):

        to_insert = {
            '_id': project_id or uuid.uuid4().hex,
            'secret_key': secret_key,
            'options': json.dumps(options)
        }

        query = "INSERT INTO projects (_id, secret_key, options) VALUES (%(_id)s, %(secret_key)s, %(options)s)"

        try:
            yield momoko.Op(
                self._pool.execute, query, to_insert
            )
        except Exception as e:
            on_error(e)
        else:
            raise Return((to_insert, None))

    @coroutine
    def project_edit(self, project, options):

        to_update = {
            '_id': extract_obj_id(project),
            'options': json.dumps(options)
        }

        query = "UPDATE projects SET options=%(options)s WHERE _id=%(_id)s"

        try:
            yield momoko.Op(
                self._pool.execute, query, to_update
            )
        except Exception as e:
            on_error(e)
        else:
            raise Return((to_update, None))

    @coroutine
    def regenerate_project_secret_key(self, project, secret_key):

        haystack = {
            '_id': extract_obj_id(project),
            'secret_key': secret_key
        }

        query = "UPDATE projects SET secret_key=%(secret_key)s WHERE _id=%(_id)s"

        try:
            yield momoko.Op(
                self._pool.execute, query, haystack,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            on_error(e)
        else:
            raise Return((secret_key, None))

    @coroutine
    def project_delete(self, project):
        """
        Delete project. Also delete all related namespaces.
        """
        haystack = {
            'project_id': extract_obj_id(project)
        }

        query = "DELETE FROM projects WHERE _id=%(project_id)s"
        try:
            yield momoko.Op(
                self._pool.execute, query, haystack
            )
        except Exception as e:
            on_error(e)

        query = "DELETE FROM namespaces WHERE project_id=%(project_id)s"
        try:
            yield momoko.Op(
                self._pool.execute, query, haystack
            )
        except Exception as e:
            on_error(e)

        raise Return((True, None))

    @coroutine
    def namespace_list(self):

        query = "SELECT * FROM namespaces"
        try:
            cursor = yield momoko.Op(
                self._pool.execute, query, {},
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            on_error(e)
        else:
            namespaces = cursor.fetchall()
            raise Return((namespaces, None))

    @coroutine
    def namespace_create(self, project, name, options, namespace_id=None):

        to_insert = {
            '_id': namespace_id or uuid.uuid4().hex,
            'project_id': extract_obj_id(project),
            'name': name,
            'options': json.dumps(options)
        }

        query = "INSERT INTO namespaces (_id, project_id, name, options) " \
                "VALUES (%(_id)s, %(project_id)s, %(name)s, %(options)s)"

        try:
            yield momoko.Op(
                self._pool.execute, query, to_insert
            )
        except Exception as e:
            on_error(e)
        else:
            raise Return((to_insert, None))

    @coroutine
    def namespace_edit(self, namespace, name, options):

        to_update = {
            '_id': namespace['_id'],
            'name': name,
            'options': json.dumps(options)
        }

        query = "UPDATE namespaces SET name=%(name)s, options=%(options)s WHERE _id=%(_id)s"

        try:
            yield momoko.Op(
                self._pool.execute, query, to_update
            )
        except Exception as e:
            on_error(e)
        else:
            raise Return((to_update, None))

    @coroutine
    def namespace_delete(self, namespace):
        haystack = {
            '_id': extract_obj_id(namespace)
        }

        query = "DELETE FROM namespaces WHERE _id=%(_id)s"

        try:
            yield momoko.Op(
                self._pool.execute, query, haystack
            )
        except Exception as e:
            on_error(e)
        else:
            raise Return((True, None))
