# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import uuid
import tornado.web
import tornado.escape
import tornado.auth
import tornado.httpclient
import tornado.gen
from tornado.gen import coroutine, Return
from tornado.web import decode_signed_value
from sockjs.tornado import SockJSConnection
from tornado.escape import json_encode

from ..log import logger
from ..handlers import BaseHandler

from .forms import ProjectForm, NamespaceForm


class LogoutHandler(BaseHandler):

    def get(self):
        self.clear_cookie("user")
        self.redirect(self.reverse_url("main"))


class AuthHandler(BaseHandler):

    def authorize(self):
        self.set_secure_cookie("user", "authorized")
        self.redirect(self.reverse_url("main"))

    def get(self):
        if not self.opts.get("password"):
            self.authorize()
        else:
            self.render('index.html')

    def post(self):
        password = self.get_argument("password", None)
        if password and password == self.opts.get("password"):
            self.authorize()
        else:
            self.render('index.html')


class MainHandler(BaseHandler):

    @tornado.web.authenticated
    @coroutine
    def get(self):
        """
        Render main template with additional data.
        Here we need information about namespaces and sources.
        Also information about watching and marked objects.
        """
        user = self.current_user.decode()

        projects, error = yield self.application.structure.project_list()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        project_namespaces, error = yield self.application.structure.get_namespaces_for_projects()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        context = {
            'js_data': tornado.escape.json_encode({
                'current_user': user,
                'socket_url': '/socket',
                'projects': projects,
                'namespaces': project_namespaces
            })
        }
        self.render("main.html", **context)


def render_control(field):
    if field.type == 'BooleanField':
        return field()
    return field(class_="form-control")


def render_label(label):
    return label(class_="col-lg-2 control-label")


class ProjectCreateHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):

        self.render(
            'project/create.html', form=ProjectForm(self),
            render_control=render_control, render_label=render_label
        )

    @tornado.web.authenticated
    @coroutine
    def post(self):
        form = ProjectForm(self)
        if not form.validate():
            self.render(
                'project/create.html', form=form,
                render_control=render_control, render_label=render_label
            )
            return

        existing_project, error = yield self.application.structure.get_project_by_name(form.name.data)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if existing_project:
            form.name.errors.append('duplicate name')
            self.render(
                'project/create.html', form=form,
                render_control=render_control, render_label=render_label
            )
            return

        project, error = yield self.application.structure.project_create(
            name=form.name.data,
            display_name=form.display_name.data,
            auth_address=form.auth_address.data,
            max_auth_attempts=form.max_auth_attempts.data,
            back_off_interval=form.back_off_interval.data,
            back_off_max_timeout=form.back_off_max_timeout.data
        )
        if error:
            raise tornado.web.HTTPError(500, log_message="error creating project")

        self.redirect(self.reverse_url('main'))


class NamespaceFormHandler(BaseHandler):

    @coroutine
    def get_project(self, project_name):
        project, error = yield self.application.structure.get_project_by_name(project_name)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if not project:
            raise tornado.web.HTTPError(404)
        raise Return((project, None))

    @coroutine
    def get_namespace(self, project, namespace_name):
        namespace, error = yield self.application.structure.get_namespace_by_name(
            project, namespace_name
        )
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if not namespace:
            raise tornado.web.HTTPError(404)
        raise Return((namespace, error))

    @tornado.web.authenticated
    @coroutine
    def get(self, project_name, namespace_name=None):

        self.project, error = yield self.get_project(project_name)

        if namespace_name:
            template_name = 'namespace/edit.html'
            self.namespace, error = yield self.get_namespace(self.project, namespace_name)
            form = NamespaceForm(self, **self.namespace)
        else:
            template_name = 'namespace/create.html'
            form = NamespaceForm(self)

        self.render(
            template_name, form=form, project=self.project,
            render_control=render_control, render_label=render_label
        )

    @tornado.web.authenticated
    @coroutine
    def post(self, project_id, namespace_name=None):

        self.project, error = yield self.get_project(project_id)

        if namespace_name:
            self.namespace, error = yield self.get_namespace(self.project, namespace_name)

        submit = self.get_argument('submit', None)
        if submit == 'namespace_delete':
            if self.get_argument('confirm', None) == namespace_name:
                res, error = yield self.application.structure.namespace_delete(
                    self.project, namespace_name
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.redirect(self.reverse_url("project_settings", self.project['name'], 'general'))
            else:
                self.redirect(self.reverse_url("namespace_edit", self.project['name'], namespace_name))
            return

        form = NamespaceForm(self)

        if not form.validate():
            self.render(
                'namespace/create.html', form=form, project=self.project,
                render_control=render_control, render_label=render_label
            )
            return

        existing_namespace, error = yield self.application.structure.get_namespace_by_name(
            self.project, form.name.data
        )
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        if (not namespace_name and existing_namespace) or (existing_namespace and existing_namespace['name'] != namespace_name):
            form.name.errors.append('duplicate name')
            self.render(
                'namespace/create.html', form=form, project=self.project,
                render_control=render_control, render_label=render_label
            )
            return

        kwargs = {
            'name': form.name.data,
            'publish': form.publish.data,
            'is_watching': form.is_watching.data,
            'presence': form.presence.data,
            'history': form.history.data,
            'history_size': form.history_size.data,
            'is_private': form.is_private.data,
            'auth_address': form.auth_address.data,
            'join_leave': form.join_leave.data
        }

        if not namespace_name:
            namespace, error = yield self.application.structure.namespace_create(
                self.project,
                **kwargs
            )
            if error:
                raise tornado.web.HTTPError(500, log_message="error creating project")
        else:
            namespace, error = yield self.application.structure.namespace_edit(
                self.namespace,
                **kwargs
            )
            if error:
                raise tornado.web.HTTPError(500, log_message="error creating project")

        self.redirect(self.reverse_url("project_settings", self.project['name'], 'general'))


class ProjectSettingsHandler(BaseHandler):
    """
    Edit project setting.
    This part of application requires more careful implementation.
    """
    @coroutine
    def get_project(self, project_name):

        project, error = yield self.application.structure.get_project_by_name(project_name)
        if not project:
            raise tornado.web.HTTPError(404)

        raise Return((project, None))

    @coroutine
    def get_general(self):
        namespaces, error = yield self.application.structure.get_project_namespaces(self.project)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        data = {
            'user': self.current_user,
            'project': self.project,
            'namespaces': namespaces
        }
        raise Return((data, None))

    @coroutine
    def post_general(self, submit):

        url = self.reverse_url("project_settings", self.project['name'], 'general')

        if submit == 'regenerate_secret':
            # regenerate public and secret key
            res, error = yield self.application.structure.regenerate_project_secret_key(self.project)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

        self.redirect(url)

    @coroutine
    def get_namespace_choices(self):
        namespaces, error = yield self.application.structure.get_project_namespaces(self.project)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        namespace_choices = [(x['_id'], x['name']) for x in namespaces]
        namespace_choices.insert(0, ('', '--------'))
        raise Return((namespace_choices, None))

    @coroutine
    def get_edit(self):
        namespace_choices, error = yield self.get_namespace_choices()
        data = {
            'user': self.current_user,
            'project': self.project,
            'form': ProjectForm(self, namespace_choices=namespace_choices, **self.project),
            'render_control': render_control,
            'render_label': render_label
        }
        raise Return((data, None))

    @coroutine
    def post_edit(self, submit):

        if submit == 'project_del':
            # completely remove project
            confirm = self.get_argument('confirm', None)
            if confirm == self.project['name']:
                res, error = yield self.application.structure.project_delete(self.project)
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.redirect(self.reverse_url("main"))
                return
            else:
                self.redirect(self.reverse_url("project_settings", self.project['name'], "edit"))

        else:
            # edit project
            namespace_choices, error = yield self.get_namespace_choices()
            form = ProjectForm(self, namespace_choices=namespace_choices)
            if not form.validate():
                self.render(
                    'project/settings_edit.html', project=self.project,
                    form=form, render_control=render_control, render_label=render_label
                )
                return

            existing_project, error = yield self.application.structure.get_project_by_name(form.name.data)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

            if existing_project and existing_project['_id'] != self.project['_id']:
                form.name.errors.append('duplicate name')
                self.render(
                    'project/settings_edit.html', form=form,
                    render_control=render_control, render_label=render_label,
                    project=self.project
                )
                return

            default_namespace = form.default_namespace.data or None

            res, error = yield self.application.structure.project_edit(
                self.project,
                name=form.name.data,
                display_name=form.display_name.data,
                auth_address=form.auth_address.data,
                max_auth_attempts=form.max_auth_attempts.data,
                back_off_interval=form.back_off_interval.data,
                back_off_max_timeout=form.back_off_max_timeout.data,
                default_namespace=default_namespace
            )
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))
            self.redirect(self.reverse_url("project_settings", form.name.data, "edit"))

    @tornado.web.authenticated
    @coroutine
    def get(self, project_name, section):

        self.project, error = yield self.get_project(project_name)

        if section == 'general':
            template_name = 'project/settings_general.html'
            func = self.get_general

        elif section == 'edit':
            template_name = 'project/settings_edit.html'
            func = self.get_edit

        else:
            raise tornado.web.HTTPError(404)

        data, error = yield func()

        self.render(template_name, **data)

    @tornado.web.authenticated
    @coroutine
    def post(self, project_name, section):

        self.project, error = yield self.get_project(
            project_name
        )

        submit = self.get_argument('submit', None)

        if section == 'general':
            yield self.post_general(submit)

        elif section == 'edit':
            yield self.post_edit(submit)

        else:
            raise tornado.web.HTTPError(404)


class AdminSocketHandler(SockJSConnection):

    @coroutine
    def subscribe(self):
        self.uid = uuid.uuid4().hex
        connections = self.application.admin_connections
        connections[self.uid] = self
        logger.info('admin connected')

    def unsubscribe(self):
        if not hasattr(self, 'uid'):
            return

        connections = self.application.admin_connections
        try:
            del connections[self.uid]
        except KeyError:
            pass

        logger.info('admin disconnected')

    def on_open(self, info):
        try:
            value = info.cookies['user'].value
        except (KeyError, AttributeError):
            self.close()
        else:
            user = decode_signed_value(
                self.application.settings['cookie_secret'], 'user', value
            )
            if user:
                self.subscribe()
            else:
                self.close()

    def on_close(self):
        self.unsubscribe()


class Http404Handler(BaseHandler):

    def get(self):
        self.render("http404.html")


class StructureDumpHandler(BaseHandler):

    @coroutine
    def get(self):
        projects, error = yield self.application.structure.project_list()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        namespaces, error = yield self.application.structure.namespace_list()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        data = {
            "projects": projects,
            "namespaces": namespaces
        }
        self.set_header("Content-Type", "application/json")
        self.finish(json_encode(data))