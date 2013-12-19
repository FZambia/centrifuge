# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

from tornado.gen import coroutine, Return
from toro import Lock

from centrifuge.log import logger


lock = Lock()

import json
import six
import uuid


def flatten(dictionary):
    options = dictionary['options']
    if isinstance(options, six.string_types):
        options = json.loads(options)
    del dictionary['options']
    dictionary.update(options)
    return dictionary


def get_projects_by_id(projects):
    to_return = {}
    for project in projects:
        to_return[project['_id']] = project
    return to_return


def get_projects_by_name(projects):
    to_return = {}
    for project in projects:
        to_return[project['name']] = project
    return to_return


def get_namespaces_by_id(namespaces):
    to_return = {}
    for namespace in namespaces:
        to_return[namespace['_id']] = namespace
    return to_return


def get_namespaces_by_name(namespaces):
    to_return = {}
    for namespace in namespaces:
        if namespace['project_id'] not in to_return:
            to_return[namespace['project_id']] = {}
        to_return[namespace['project_id']][namespace['name']] = namespace
    return to_return


def get_project_namespaces(namespaces):
    to_return = {}
    for namespace in namespaces:
        if namespace['project_id'] not in to_return:
            to_return[namespace['project_id']] = []
        to_return[namespace['project_id']].append(namespace)
    return to_return


class InconsistentStructureError(Exception):

    def __str__(self):
        return 'inconsistent structure error'


class Structure:

    def __init__(self, application):
        self.application = application
        self.storage = None
        self.db = None
        self._consistent = False
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
        self._consistent = False
        raise Return((None, error))

    def set_consistency(self, value):
        self._consistent = value

    def is_consistent(self):
        return self._consistent

    @coroutine
    def update(self):
        """
        Call this method periodically to keep structure consistency
        """
        if not self.storage or not self.db:
            raise Return((True, None))

        with (yield lock.acquire()):
            raw_projects, error = yield self.storage.project_list(self.db)
            if error:
                self.on_error(error)
            projects = [flatten(x) for x in raw_projects]

            raw_namespaces, error = yield self.storage.namespace_list(self.db)
            if error:
                self.on_error(error)
            namespaces = [flatten(x) for x in raw_namespaces]

            projects_by_id = get_projects_by_id(projects)
            projects_by_name = get_projects_by_name(projects)
            namespaces_by_id = get_namespaces_by_id(namespaces)
            namespaces_by_name = get_namespaces_by_name(namespaces)
            project_namespaces = get_project_namespaces(namespaces)

            self._data = {
                'projects': projects,
                'namespaces': namespaces,
                'projects_by_id': projects_by_id,
                'projects_by_name': projects_by_name,
                'namespaces_by_id': namespaces_by_id,
                'namespaces_by_name': namespaces_by_name,
                'project_namespaces': project_namespaces
            }

            self._consistent = True

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
        message = {
            "app_id": self.application.uid,
            "method": "update_structure",
            "params": {}
        }
        self.application.send_control_message(message)

        # update structure of current instance
        success, error = yield self.update()
        if error:
            self.on_error(error)
        raise Return((result, error))

    @coroutine
    def project_create(self, **kwargs):

        options = {
            "name": kwargs['name'],
            "display_name": kwargs['display_name'],
            "auth_address": kwargs['auth_address'],
            "max_auth_attempts": kwargs['max_auth_attempts'],
            "back_off_interval": kwargs['back_off_interval'],
            "back_off_max_timeout": kwargs['back_off_max_timeout'],
            "default_namespace": None
        }
        result, error = yield self.call_and_update_structure(
            'project_create', uuid.uuid4().hex, options
        )
        raise Return((result, error))

    @coroutine
    def project_edit(self, project, **kwargs):

        options = {
            'name': kwargs['name'],
            'display_name': kwargs['display_name'],
            'auth_address': kwargs['auth_address'],
            'max_auth_attempts': kwargs['max_auth_attempts'],
            'back_off_interval': kwargs['back_off_interval'],
            'back_off_max_timeout': kwargs['back_off_max_timeout'],
            'default_namespace': kwargs['default_namespace']
        }

        result, error = yield self.call_and_update_structure(
            'project_edit', project, options
        )
        raise Return((result, error))

    @coroutine
    def regenerate_project_secret_key(self, project):
        secret_key = uuid.uuid4().hex
        result, error = yield self.call_and_update_structure(
            'regenerate_project_secret_key', project, secret_key
        )
        raise Return((result, error))

    @coroutine
    def project_delete(self, project):
        result, error = yield self.call_and_update_structure(
            'project_delete', project
        )
        raise Return((result, error))

    @coroutine
    def namespace_create(self, project, **kwargs):

        options = {
            'publish': kwargs['publish'],
            'is_watching': kwargs['is_watching'],
            'presence': kwargs['presence'],
            'history': kwargs['history'],
            'history_size': kwargs['history_size'],
            'is_private': kwargs['is_private'],
            'auth_address': kwargs['auth_address'],
            'join_leave': kwargs['join_leave']
        }

        result, error = yield self.call_and_update_structure(
            'namespace_create', project, kwargs['name'], options
        )
        raise Return((result, error))

    @coroutine
    def namespace_edit(self, namespace, **kwargs):

        options = {
            'publish': kwargs['publish'],
            'is_watching': kwargs['is_watching'],
            'presence': kwargs['presence'],
            'history': kwargs['history'],
            'history_size': kwargs['history_size'],
            'is_private': kwargs['is_private'],
            'auth_address': kwargs['auth_address'],
            'join_leave': kwargs['join_leave']
        }

        result, error = yield self.call_and_update_structure(
            'namespace_edit', namespace, kwargs["name"], options
        )
        raise Return((result, error))

    @coroutine
    def namespace_delete(self, namespace):
        result, error = yield self.call_and_update_structure(
            'namespace_delete', namespace
        )
        raise Return((result, error))
