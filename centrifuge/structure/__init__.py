# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

from tornado.gen import coroutine, Return
from toro import Lock
from tornado.ioloop import PeriodicCallback

from centrifuge.log import logger
from centrifuge import forms

lock = Lock()

import json
import six
import uuid


def flatten(dictionary):
    """
    Transform dictionary with `options` key to plain dictionary with
    simple key-value structure.
    """
    if not isinstance(dictionary, dict):
        return dictionary
    options = dictionary.get('options')
    if options:
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


class Structure:

    def __init__(self, application):
        self.application = application
        self.storage = None
        self._consistent = False
        self._uid = None
        self.recover_interval = 1000
        self.structure_recover = PeriodicCallback(
            self.update_structure_because_of_inconsistency,
            self.recover_interval
        )
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

    @coroutine
    def update_structure_because_of_inconsistency(self):
        # try to update structure at least after a second
        logger.error("structure inconsistent, will try to update after {0} milliseconds".format(
            self.recover_interval
        ))
        self.structure_recover.stop()
        yield self.update()

    def on_error(self, error):
        logger.error(error)
        self._consistent = False
        self.structure_recover.start()
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
        if not self.storage:
            raise Return((True, None))

        with (yield lock.acquire()):
            raw_projects, error = yield self.storage.project_list()
            if error:
                self.on_error(error)

            projects = [flatten(x) for x in raw_projects]

            raw_namespaces, error = yield self.storage.namespace_list()
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
            self.structure_recover.stop()

            logger.debug('Structure updated')

            raise Return((True, None))

    @coroutine
    def clear_structure(self):
        result, error = yield self.call_and_update_structure(
            'clear_structure'
        )
        raise Return((result, error))

    @coroutine
    def project_list(self):
        with (yield lock.acquire()):
            raise Return((self._data['projects'], None))

    @coroutine
    def namespace_list(self):
        with (yield lock.acquire()):
            raise Return((self._data['namespaces'], None))

    @coroutine
    def get_namespaces_for_projects(self):
        with (yield lock.acquire()):
            raise Return((self._data['project_namespaces'], None))

    @coroutine
    def get_project_namespaces(self, project):
        with (yield lock.acquire()):
            raise Return((
                self._data['project_namespaces'].get(project['_id'], []),
                None
            ))

    @coroutine
    def get_project_by_id(self, project_id):
        with (yield lock.acquire()):
            raise Return((
                self._data['projects_by_id'].get(project_id),
                None
            ))

    @coroutine
    def get_project_by_name(self, project_name):
        with (yield lock.acquire()):
            raise Return((
                self._data['projects_by_name'].get(project_name),
                None
            ))

    @coroutine
    def get_namespace_by_id(self, namespace_id):
        with (yield lock.acquire()):
            raise Return((
                self._data['namespaces_by_id'].get(namespace_id),
                None
            ))

    @coroutine
    def get_namespaces_by_name(self):
        with (yield lock.acquire()):
            raise Return((
                self._data['namespaces_by_name'],
                None
            ))

    @coroutine
    def get_namespace_by_name(self, project, namespace_name):
        with (yield lock.acquire()):
            namespace = self._data['namespaces_by_name'].get(
                project['_id'], {}
            ).get(namespace_name, None)

            raise Return((namespace, None))

    @coroutine
    def call_and_update_structure(self, func_name, *args, **kwargs):

        # call storage function
        func = getattr(self.storage, func_name, None)
        assert func, 'function {0} not found in storage' % func_name
        result, error = yield func(*args, **kwargs)
        if error:
            self.on_error(error)

        # share knowledge about required structure update with all system
        message = {
            "app_id": self.application.uid,
            "method": "update_structure",
            "params": {}
        }
        self.application.engine.publish_control_message(message)

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
            "connection_check": kwargs.get("connection_check", False),
            "connection_lifetime": kwargs.get('connection_lifetime', forms.DEFAULT_CONNECTION_LIFETIME),
            "connection_check_interval": kwargs.get('connection_check_interval', forms.DEFAULT_CONNECTION_CHECK_INTERVAL),
            "connection_check_address": kwargs.get('connection_check_address', ''),
            "max_auth_attempts": kwargs.get('max_auth_attempts', forms.DEFAULT_MAX_AUTH_ATTEMPTS),
            "back_off_interval": kwargs.get('back_off_interval', forms.DEFAULT_BACK_OFF_INTERVAL),
            "back_off_max_timeout": kwargs.get('back_off_max_timeout', forms.DEFAULT_BACK_OFF_MAX_TIMEOUT),
            'publish': kwargs.get('publish', False),
            'is_watching': kwargs.get('is_watching', True),
            'anonymous': kwargs.get('anonymous', False),
            'presence': kwargs.get('presence', True),
            'history': kwargs.get('history', True),
            'history_size': kwargs.get('history_size', forms.DEFAULT_HISTORY_SIZE),
            'history_expire': kwargs.get('history_expire', forms.DEFAULT_HISTORY_EXPIRE),
            'is_private': kwargs.get('is_private', False),
            'auth_address': kwargs.get('auth_address', ''),
            'join_leave': kwargs.get('join_leave', True)
        }

        secret_key = uuid.uuid4().hex
        if "secret_key" in kwargs:
            secret_key = kwargs["secret_key"]

        result, error = yield self.call_and_update_structure(
            'project_create', secret_key, options, project_id=kwargs.get('_id')
        )
        raise Return((flatten(result), error))

    @coroutine
    def project_edit(self, project, **kwargs):

        options = {
            'name': kwargs['name'],
            'display_name': kwargs['display_name'],
            "connection_check": kwargs.get("connection_check", False),
            "connection_lifetime": kwargs.get('connection_lifetime', forms.DEFAULT_CONNECTION_LIFETIME),
            "connection_check_interval": kwargs.get('connection_check_interval', forms.DEFAULT_CONNECTION_CHECK_INTERVAL),
            "connection_check_address": kwargs.get('connection_check_address', ''),
            "max_auth_attempts": kwargs.get('max_auth_attempts', forms.DEFAULT_MAX_AUTH_ATTEMPTS),
            "back_off_interval": kwargs.get('back_off_interval', forms.DEFAULT_BACK_OFF_INTERVAL),
            "back_off_max_timeout": kwargs.get('back_off_max_timeout', forms.DEFAULT_BACK_OFF_MAX_TIMEOUT),
            'publish': kwargs.get('publish', False),
            'is_watching': kwargs.get('is_watching', True),
            'anonymous': kwargs.get('anonymous', False),
            'presence': kwargs.get('presence', True),
            'history': kwargs.get('history', True),
            'history_size': kwargs.get('history_size', forms.DEFAULT_HISTORY_SIZE),
            'history_expire': kwargs.get('history_expire', forms.DEFAULT_HISTORY_EXPIRE),
            'is_private': kwargs.get('is_private', False),
            'auth_address': kwargs.get('auth_address', ''),
            'join_leave': kwargs.get('join_leave', True)
        }

        result, error = yield self.call_and_update_structure(
            'project_edit', project, options
        )
        raise Return((flatten(result), error))

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
            'publish': kwargs.get('publish', False),
            'is_watching': kwargs.get('is_watching', True),
            'anonymous': kwargs.get('anonymous', False),
            'presence': kwargs.get('presence', True),
            'history': kwargs.get('history', True),
            'history_size': kwargs.get('history_size', forms.DEFAULT_HISTORY_SIZE),
            'history_expire': kwargs.get('history_expire', forms.DEFAULT_HISTORY_EXPIRE),
            'is_private': kwargs.get('is_private', False),
            'auth_address': kwargs.get('auth_address', ''),
            'join_leave': kwargs.get('join_leave', True)
        }

        result, error = yield self.call_and_update_structure(
            'namespace_create', project, kwargs['name'], options, namespace_id=kwargs.get('_id')
        )
        raise Return((flatten(result), error))

    @coroutine
    def namespace_edit(self, namespace, **kwargs):

        options = {
            'publish': kwargs.get('publish', False),
            'is_watching': kwargs.get('is_watching', True),
            'anonymous': kwargs.get('anonymous', False),
            'presence': kwargs.get('presence', True),
            'history': kwargs.get('history', True),
            'history_size': kwargs.get('history_size', forms.DEFAULT_HISTORY_SIZE),
            'history_expire': kwargs.get('history_expire', forms.DEFAULT_HISTORY_EXPIRE),
            'is_private': kwargs.get('is_private', False),
            'auth_address': kwargs.get('auth_address', ''),
            'join_leave': kwargs.get('join_leave', True)
        }

        result, error = yield self.call_and_update_structure(
            'namespace_edit', namespace, kwargs["name"], options
        )
        raise Return((flatten(result), error))

    @coroutine
    def namespace_delete(self, namespace):
        result, error = yield self.call_and_update_structure(
            'namespace_delete', namespace
        )
        raise Return((result, error))


class BaseStorage(object):

    NAME = "Abstract base storage"

    def __init__(self, options):
        self.options = options

    def connect(self, callback=None):
        raise NotImplementedError()

    def clear_structure(self):
        raise NotImplementedError()

    def project_list(self):
        raise NotImplementedError()

    def namespace_list(self):
        raise NotImplementedError()

    def project_create(self, secret_key, options, project_id=None):
        raise NotImplementedError()

    def project_edit(self, project, options):
        raise NotImplementedError()

    def project_delete(self, project):
        raise NotImplementedError()

    def regenerate_project_secret_key(self, project, secret_key):
        raise NotImplementedError()

    def namespace_create(self, project, name, options, namespace_id=None):
        raise NotImplementedError()

    def namespace_edit(self, namespace, name, options):
        raise NotImplementedError()

    def namespace_delete(self, namespace):
        raise NotImplementedError()


