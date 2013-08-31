# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.gen import coroutine, Return
from tornado.escape import json_encode
from toro import Lock

from .. import auth
from ..log import logger


lock = Lock()


class InconsistentStructureError(Exception):

    def __str__(self):
        return 'inconsistent structure error'


class Structure:

    _CONSISTENT = False

    def __init__(self, application):
        self.application = application
        self.storage = None
        self.db = None
        self._uid = None
        self._data = {
            'projects': [],
            'namespaces': [],
            'projects_by_id': {},
            'projects_by_name': {},
            'namespaces_by_id': {},
            'namespaces_by_name': {},
            'project_namespaces': {}
        }

    def set_storage(self, storage):
        self.storage = storage

    def set_db(self, db):
        self.db = db

    def on_error(self, error):
        logger.error(str(error))
        self._CONSISTENT = False
        raise Return((None, error))

    def on_update_success(self):
        self._CONSISTENT = True

    def is_consistent(self):
        return self._CONSISTENT

    @coroutine
    def update(self):
        """
        Call this method periodically to keep structure consistency
        """
        if not self.storage or not self.db:
            raise Return((True, None))

        with (yield lock.acquire()):

            projects, error = yield self.storage.project_list(self.db)
            if error:
                self.on_error(error)

            namespaces, error = yield self.storage.namespace_list(self.db)
            if error:
                self.on_error(error)

            projects_by_id = self.storage.projects_by_id(projects)
            projects_by_name = self.storage.projects_by_name(projects)
            namespaces_by_id = self.storage.namespaces_by_id(namespaces)
            namespaces_by_name = self.storage.namespaces_by_name(namespaces)
            project_namespaces = self.storage.project_namespaces(namespaces)

            self._data = {
                'projects': projects,
                'namespaces': namespaces,
                'projects_by_id': projects_by_id,
                'projects_by_name': projects_by_name,
                'namespaces_by_id': namespaces_by_id,
                'namespaces_by_name': namespaces_by_name,
                'project_namespaces': project_namespaces
            }

            self._CONSISTENT = True

            logger.debug('Structure updated')

            raise Return((True, None))

    @coroutine
    def project_list(self):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStructureError()))
            raise Return((self._data['projects'], None))

    @coroutine
    def namespace_list(self):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStructureError()))
            raise Return((self._data['namespaces'], None))

    @coroutine
    def get_namespaces_for_projects(self):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStructureError()))
            raise Return((self._data['project_namespaces'], None))

    @coroutine
    def get_project_namespaces(self, project):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStructureError()))
            raise Return((
                self._data['project_namespaces'].get(project['_id'], []),
                None
            ))

    @coroutine
    def get_project_by_id(self, project_id):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStructureError()))
            raise Return((
                self._data['projects_by_id'].get(project_id),
                None
            ))

    @coroutine
    def get_project_by_name(self, project_name):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStructureError()))
            raise Return((
                self._data['projects_by_name'].get(project_name),
                None
            ))

    @coroutine
    def get_namespace_by_id(self, namespace_id):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStructureError()))
            raise Return((
                self._data['namespaces_by_id'].get(namespace_id),
                None
            ))

    @coroutine
    def get_namespaces_by_name(self):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStructureError()))
            raise Return((
                self._data['namespaces_by_name'],
                None
            ))

    @coroutine
    def get_namespace_by_name(self, project, namespace_name):
        if namespace_name is None:
            default_namespace = project.get('default_namespace')
            if not default_namespace:
                raise Return((None, None))
            else:
                namespace, error = yield self.get_namespace_by_id(default_namespace)
                raise Return((namespace, error))

        else:
            with (yield lock.acquire()):
                if not self.is_consistent():
                    raise Return((None, InconsistentStructureError()))

                raise Return((
                    self._data['namespaces_by_name'].get(
                        project['_id'], {}
                    ).get(namespace_name),
                    None
                ))

    @coroutine
    def call_and_update_structure(self, func_name, *args, **kwargs):

        # call storage function
        func = getattr(self.storage, func_name, None)
        assert func, 'function {0} not found in storage' % func_name
        result, error = yield func(self.db, *args, **kwargs)
        if error:
            self.on_error(error)

        # share knowledge about required structure update with all system
        message = json_encode({
            "app_id": self.application.uid,
            "method": "update_structure",
            "params": {}
        })
        self.application.send_control_message(message)

        # update structure of current instance
        success, error = yield self.update()
        if error:
            self.on_error(error)
        raise Return((result, error))

    @coroutine
    def project_create(self, *args, **kwargs):
        result, error = yield self.call_and_update_structure(
            'project_create', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def project_edit(self, *args, **kwargs):
        result, error = yield self.call_and_update_structure(
            'project_edit', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def project_delete(self, *args, **kwargs):
        result, error = yield self.call_and_update_structure(
            'project_delete', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def namespace_create(self, *args, **kwargs):
        result, error = yield self.call_and_update_structure(
            'namespace_create', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def namespace_edit(self, *args, **kwargs):
        result, error = yield self.call_and_update_structure(
            'namespace_edit', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def namespace_delete(self, *args, **kwargs):
        result, error = yield self.call_and_update_structure(
            'namespace_delete', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def regenerate_project_secret_key(self, *args, **kwargs):
        result, error = yield self.call_and_update_structure(
            'regenerate_project_secret_key', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def check_auth(self, project, sign, encoded_data):
        is_authenticated = auth.check_sign(
            project['secret_key'],
            project['_id'],
            encoded_data,
            sign
        )
        if not is_authenticated:
            raise Return((None, None))

        raise Return((True, None))
