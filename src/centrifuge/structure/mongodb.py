# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import uuid
import motor
from tornado.gen import Task, coroutine, Return

from centrifuge.structure import BaseStorage


NAME = "MongoDB"


def on_error(error):
    raise Return((None, error))


def extract_obj_id(obj):
    return obj['_id']


@coroutine
def insert(collection, data):
    """
    Insert data into collection.
    """
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


class Storage(BaseStorage):

    NAME = "MongoDB"

    def __init__(self, *args, **kwargs):
        super(Storage, self).__init__(*args, **kwargs)
        self._conn = None

    def open_connection(self):
        self._conn = motor.MotorClient(
            host=self.settings.get("host", "localhost"),
            port=self.settings.get("port", 27017)
        ).open_sync()[self.settings.get("name", "centrifuge")]

    def ensure_indexes(self, drop=False):
        if drop:
            self._conn.project.drop_indexes()
            self._conn.namespace.drop_indexes()
        self._conn.namespace.ensure_index([('name', 1), ('project_id', 1)], unique=True)

    def connect(self, callback=None):
        self.open_connection()
        self.ensure_indexes()
        callback()

    @coroutine
    def clear_structure(self):
        try:
            yield Task(self._conn.drop_collection, "project")
            yield Task(self._conn.drop_collection, "namespace")
        except Exception as err:
            raise Return((None, err))
        raise Return((True, None))

    @coroutine
    def project_list(self):

        projects, error = yield find(self._conn.project, {})
        if error:
            on_error(error)

        raise Return((projects, None))

    @coroutine
    def project_create(self, secret_key, options, project_id=None):

        to_insert = {
            '_id': project_id or uuid.uuid4().hex,
            'secret_key': secret_key,
            'options': options
        }
        result, error = yield insert(self._conn.project, to_insert)
        if error:
            on_error(error)
            return
        raise Return((to_insert, None))

    @coroutine
    def project_edit(self, project, options):

        to_update = {
            'options': options
        }
        _res, error = yield update(
            self._conn.project,
            {'_id': extract_obj_id(project)},
            to_update
        )
        if error:
            on_error(error)

        raise Return((True, None))

    @coroutine
    def regenerate_project_secret_key(self, project, secret_key):

        haystack = {
            '_id': extract_obj_id(project)
        }
        update_data = {
            'secret_key': secret_key
        }
        result, error = yield update(self._conn.project, haystack, update_data)
        if error:
            on_error(error)

        raise Return((update_data, None))

    @coroutine
    def project_delete(self, project):
        """
        Delete project. Also delete all related namespaces.
        """
        haystack = {
            '_id': extract_obj_id(project)
        }
        _res, error = yield remove(self._conn.project, haystack)
        if error:
            on_error(error)

        haystack = {
            'project_id': extract_obj_id(project)
        }
        _res, error = yield remove(self._conn.namespace, haystack)
        if error:
            on_error(error)

        raise Return((True, None))

    @coroutine
    def namespace_list(self):

        namespaces, error = yield find(self._conn.namespace, {})
        if error:
            on_error(error)

        raise Return((namespaces, None))

    @coroutine
    def namespace_create(self, project, name, options, namespace_id=None):

        haystack = {
            '_id': namespace_id or uuid.uuid4().hex,
            'project_id': extract_obj_id(project),
            'name': name,
            'options': options
        }
        namespace, error = yield insert(self._conn.namespace, haystack)
        if error:
            on_error(error)

        raise Return((haystack, None))

    @coroutine
    def namespace_edit(self, namespace, name, options):

        to_update = {
            'name': name,
            'options': options
        }
        _res, error = yield update(
            self._conn.namespace,
            {'_id': extract_obj_id(namespace)},
            to_update
        )
        if error:
            on_error(error)

        raise Return((namespace, None))

    @coroutine
    def namespace_delete(self, namespace):

        haystack = {
            '_id': extract_obj_id(namespace)
        }
        _res, error = yield remove(self._conn.namespace, haystack)
        if error:
            on_error(error)

        raise Return((True, None))
