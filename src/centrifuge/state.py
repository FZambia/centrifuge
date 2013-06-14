# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
from tornado.gen import coroutine, Return
from toro import Lock


lock = Lock()


class InconsistentStateError(Exception):
    pass


class State:

    _CONSISTENT = False

    def __init__(self, application):
        self.application = application
        self.storage = None
        self.db = None
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

    @coroutine
    def update(self):
        """
        Call this method periodically to keep state consistency
        """
        if not self.storage or not self.db:
            raise Return((True, None))

        with (yield lock.acquire()):

            projects = yield self.storage.project_list()
            categories = yield self.storage.category_list()

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

    @coroutine
    def get_project_list(self):
        with (yield lock.acquire()):
            if not self._CONSISTENT:
                raise Return((None, InconsistentStateError()))
            raise Return((self._data['projects'], None))

    @coroutine
    def get_category_list(self):
        with (yield lock.acquire()):
            if not self._CONSISTENT:
                raise Return((None, InconsistentStateError()))
            raise Return((self._data['categories'], None))

    @coroutine
    def get_project_categories(self, project_id):
        with (yield lock.acquire()):
            if not self._CONSISTENT:
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['project_categories'].get(project_id, []),
                None
            ))

    @coroutine
    def get_project_by_id(self, project_id):
        with (yield lock.acquire()):
            if not self._CONSISTENT:
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['projects_by_id'].get(project_id, {}),
                None
            ))

    @coroutine
    def get_project_by_name(self, project_name):
        with (yield lock.acquire()):
            if not self._CONSISTENT:
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['projects_by_name'].get(project_name, {}),
                None
            ))

    @coroutine
    def get_category_by_id(self, category_id):
        with (yield lock.acquire()):
            if not self._CONSISTENT:
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['categories_by_id'].get(category_id, {}),
                None
            ))

    @coroutine
    def get_category_by_name(self, category_name):
        with (yield lock.acquire()):
            if not self._CONSISTENT:
                raise Return((None, InconsistentStateError()))
            raise Return((
                self._data['categories_by_name'].get(category_name, {}),
                None
            ))

    @coroutine
    def project_create(self, name, display_name, description, validate_url):
        yield self.update()

    @coroutine
    def project_edit(self):
        yield self.update()

    @coroutine
    def project_delete(self):
        yield self.update()

    @coroutine
    def category_create(self):
        yield self.update()

    @coroutine
    def category_edit(self):
        yield self.update()

    @coroutine
    def category_delete(self):
        yield self.update()