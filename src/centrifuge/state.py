# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
from tornado.gen import coroutine, Return
from tornado.escape import json_encode
from toro import Lock

from . import auth
from .log import logger
from .rpc import publish, CONTROL_CHANNEL_NAME


lock = Lock()


class InconsistentStateError(Exception):

    def __str__(self):
        return 'inconsistent state error'


class State:

    _CONSISTENT = False

    def __init__(self, application):
        self.application = application
        self.storage = None
        self.db = None
        self._uid = None
        self._data = {
            'projects': [],
            'categories': [],
            'projects_by_id': {},
            'projects_by_name': {},
            'categories_by_id': {},
            'categories_by_name': {},
            'project_categories': {}
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
        Call this method periodically to keep state consistency
        """
        if not self.storage or not self.db:
            raise Return((True, None))

        with (yield lock.acquire()):

            projects, error = yield self.storage.project_list(self.db)
            if error:
                self.on_error(error)

            categories, error = yield self.storage.category_list(self.db)
            if error:
                self.on_error(error)

            projects_by_id = self.storage.projects_by_id(projects)
            projects_by_name = self.storage.projects_by_name(projects)
            categories_by_id = self.storage.categories_by_id(categories)
            categories_by_name = self.storage.categories_by_name(categories)
            project_categories = self.storage.project_categories(categories)

            self._data = {
                'projects': projects,
                'categories': categories,
                'projects_by_id': projects_by_id,
                'projects_by_name': projects_by_name,
                'categories_by_id': categories_by_id,
                'categories_by_name': categories_by_name,
                'project_categories': project_categories
            }

            self._CONSISTENT = True

            logger.debug('State updated')

            raise Return((True, None))

    @coroutine
    def project_list(self):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStateError()))
            raise Return((self._data['projects'], None))

    @coroutine
    def category_list(self):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStateError()))
            raise Return((self._data['categories'], None))

    @coroutine
    def get_categories_for_projects(self):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStateError()))
            raise Return((self._data['project_categories'], None))

    @coroutine
    def get_project_categories(self, project):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['project_categories'].get(project['_id'], []),
                None
            ))

    @coroutine
    def get_project_by_id(self, project_id):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['projects_by_id'].get(project_id),
                None
            ))

    @coroutine
    def get_project_by_name(self, project_name):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['projects_by_name'].get(project_name),
                None
            ))

    @coroutine
    def get_category_by_id(self, category_id):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['categories_by_id'].get(category_id),
                None
            ))

    @coroutine
    def get_category_by_name(self, project, category_name):
        with (yield lock.acquire()):
            if not self.is_consistent():
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['categories_by_name'].get(
                    project['_id'], {}
                ).get(category_name),
                None
            ))

    @coroutine
    def call_and_update_state(self, func_name, *args, **kwargs):

        # call storage function
        func = getattr(self.storage, func_name, None)
        assert func, 'function {0} not found in storage' % func_name
        result, error = yield func(self.db, *args, **kwargs)
        if error:
            self.on_error(error)

        # share knowledge about required state update with all system
        message = json_encode({
            "app_id": self.application.uid,
            "method": "update_state",
            "params": {}
        })
        publish(
            self.application.pub_stream, CONTROL_CHANNEL_NAME, message
        )

        # update state of current instance
        success, error = yield self.update()
        if error:
            self.on_error(error)
        raise Return((result, error))

    @coroutine
    def project_create(self, *args, **kwargs):
        result, error = yield self.call_and_update_state(
            'project_create', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def project_edit(self, *args, **kwargs):
        result, error = yield self.call_and_update_state(
            'project_edit', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def project_delete(self, *args, **kwargs):
        result, error = yield self.call_and_update_state(
            'project_delete', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def category_create(self, *args, **kwargs):
        result, error = yield self.call_and_update_state(
            'category_create', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def category_edit(self, *args, **kwargs):
        result, error = yield self.call_and_update_state(
            'category_edit', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def category_delete(self, *args, **kwargs):
        result, error = yield self.call_and_update_state(
            'category_delete', *args, **kwargs
        )
        raise Return((result, error))

    @coroutine
    def regenerate_project_secret_key(self, *args, **kwargs):
        result, error = yield self.call_and_update_state(
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
