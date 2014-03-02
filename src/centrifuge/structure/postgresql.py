# coding: utf-8
#
# Copyright (c) Alexandr Emelin. MIT license.
# All rights reserved.

import json
import os
import uuid

try:
    import urlparse
except ImportError:
    import urllib.parse as urlparse

from tornado.gen import coroutine, Return
import momoko
import psycopg2
import psycopg2.extras

from centrifuge.structure import BaseStorage
from centrifuge.log import logger

# Register database schemes in URLs.
urlparse.uses_netloc.append('postgres')
urlparse.uses_netloc.append('postgresql')


def extract_obj_id(obj):
    return obj['_id']


def parse_database_url(url):
    url = urlparse.urlparse(url)
    path = url.path[1:]
    path = path.split('?', 2)[0]
    return {
        "name": path,
        "user": url.username or "",
        "password": url.password or "",
        "host": url.hostname or "",
        "port": url.port or 5432
    }


class Storage(BaseStorage):

    NAME = "PostgreSQL"

    def __init__(self, *args, **kwargs):
        super(Storage, self).__init__(*args, **kwargs)
        self._conn = None

    def handle_error(self, error):
        if isinstance(error, (psycopg2.DatabaseError, psycopg2.InterfaceError)):
            self.open_connection()
        raise Return((None, error))

    def get_dsn(self):
        if "url" in self.settings:
            database_url = self.settings["url"]
            if database_url.startswith("$"):
                # Retrieve $VARIABLE_NAME from OS Environment
                database_url = os.environ[database_url[1:]]
            config = parse_database_url(database_url)
        else:
            config = {
                "name": self.settings.get("name", "centrifuge"),
                "user": self.settings.get("user", "postgres"),
                "password": self.settings.get("password", ""),
                "host": self.settings.get("host", "localhost"),
                "port": self.settings.get("port", 5432)
            }
        dsn = "dbname={name} user={user} password={password} host={host} port={port}".format(**config)
        return dsn

    def open_connection(self, callback=None):
        dsn = self.get_dsn()
        self._conn = momoko.Connection(
            dsn=dsn, callback=callback
        )

    def connect(self, callback=None):

        def on_connection_opened(conn, err):
            self.on_connection_ready(callback)

        self.open_connection(callback=on_connection_opened)

    @coroutine
    def on_connection_ready(self, ready_callback):
        project = 'CREATE TABLE IF NOT EXISTS projects (id SERIAL, _id varchar(32) UNIQUE, ' \
                  'secret_key varchar(32), options text)'

        namespace = 'CREATE TABLE IF NOT EXISTS namespaces (id SERIAL, ' \
                    '_id varchar(32) UNIQUE, project_id varchar(32), ' \
                    'name varchar(100) NOT NULL, options text, ' \
                    'constraint namespaces_unique unique(project_id, name))'

        try:
            yield momoko.Op(self._conn.execute, project, ())
            yield momoko.Op(self._conn.execute, namespace, ())
        except Exception as err:
            logger.exception(err)
        if ready_callback:
            ready_callback()

    @coroutine
    def clear_structure(self):
        project = "DELETE FROM projects"
        namespace = "DELETE FROM namespaces"
        try:
            yield momoko.Op(self._conn.execute, project, ())
            yield momoko.Op(self._conn.execute, namespace, ())
        except Exception as err:
            raise Return((None, err))
        raise Return((True, None))

    @coroutine
    def project_list(self):

        query = "SELECT * FROM projects"
        try:
            cursor = yield momoko.Op(
                self._conn.execute, query, {},
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            self.handle_error(e)
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
                self._conn.execute, query, to_insert
            )
        except Exception as e:
            self.handle_error(e)
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
                self._conn.execute, query, to_update
            )
        except Exception as e:
            self.handle_error(e)
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
                self._conn.execute, query, haystack,
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            self.handle_error(e)
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
                self._conn.execute, query, haystack
            )
        except Exception as e:
            self.handle_error(e)

        query = "DELETE FROM namespaces WHERE project_id=%(project_id)s"
        try:
            yield momoko.Op(
                self._conn.execute, query, haystack
            )
        except Exception as e:
            self.handle_error(e)

        raise Return((True, None))

    @coroutine
    def namespace_list(self):

        query = "SELECT * FROM namespaces"
        try:
            cursor = yield momoko.Op(
                self._conn.execute, query, {},
                cursor_factory=psycopg2.extras.RealDictCursor
            )
        except Exception as e:
            self.handle_error(e)
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
                self._conn.execute, query, to_insert
            )
        except Exception as e:
            self.handle_error(e)
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
                self._conn.execute, query, to_update
            )
        except Exception as e:
            self.handle_error(e)
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
                self._conn.execute, query, haystack
            )
        except Exception as e:
            self.handle_error(e)
        else:
            raise Return((True, None))
