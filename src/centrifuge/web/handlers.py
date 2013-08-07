# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import uuid
import tornado.web
import tornado.escape
import tornado.auth
import tornado.httpclient
import tornado.gen
from tornado.gen import coroutine, Return

from tornado.web import decode_signed_value
from sockjs.tornado import SockJSConnection

import six

import zmq
from zmq.eventloop.zmqstream import ZMQStream

from ..log import logger
from ..handlers import BaseHandler
from ..core import ADMIN_CHANNEL

from .forms import ProjectForm, CategoryForm


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
        Here we need information about categories and sources.
        Also information about watching and marked objects.
        """
        user = self.current_user

        projects, error = yield self.application.structure.project_list()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        project_categories, error = yield self.application.structure.get_categories_for_projects()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        context = {
            'js_data': tornado.escape.json_encode({
                'current_user': user,
                'socket_url': '/socket',
                'projects': projects,
                'categories': project_categories
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
            form.name.data,
            form.display_name.data,
            '',
            form.auth_address.data,
            form.max_auth_attempts.data,
            form.back_off_interval.data,
            form.back_off_max_timeout.data
        )
        if error:
            raise tornado.web.HTTPError(500, log_message="error creating project")

        self.redirect(self.reverse_url('main'))


class CategoryFormHandler(BaseHandler):

    @coroutine
    def get_project(self, project_name):
        project, error = yield self.application.structure.get_project_by_name(project_name)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if not project:
            raise tornado.web.HTTPError(404)
        raise Return((project, None))

    @coroutine
    def get_category(self, project, category_name):
        category, error = yield self.application.structure.get_category_by_name(
            project, category_name
        )
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if not category:
            raise tornado.web.HTTPError(404)
        raise Return((category, error))

    @tornado.web.authenticated
    @coroutine
    def get(self, project_name, category_name=None):

        self.project, error = yield self.get_project(project_name)

        if category_name:
            self.category, error = yield self.get_category(self.project, category_name)
            form = CategoryForm(self, **self.category)
        else:
            form = CategoryForm(self)

        self.render(
            'category/create.html', form=form, project=self.project,
            render_control=render_control, render_label=render_label
        )

    @tornado.web.authenticated
    @coroutine
    def post(self, project_id, category_id=None):

        self.project, error = yield self.get_project(project_id)

        if category_id:
            self.category, error = yield self.get_category(category_id)

        form = CategoryForm(self)

        if not form.validate():
            self.render(
                'category/create.html', form=form, project=self.project,
                render_control=render_control, render_label=render_label
            )
            return

        existing_category, error = yield self.application.structure.get_category_by_name(
            self.project, form.name.data
        )
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        if (not category_id and existing_category) or (existing_category and existing_category['_id'] != category_id):
            form.name.errors.append('duplicate name')
            self.render(
                'category/create.html', form=form, project=self.project,
                render_control=render_control, render_label=render_label
            )
            return

        args = (
            form.name.data,
            form.is_bidirectional.data,
            form.is_monitored.data,
            form.presence.data,
            form.presence_ping_interval.data,
            form.presence_expire_interval.data,
            form.history.data,
            form.history_size.data
        )

        if not category_id:
            category, error = yield self.application.structure.category_create(
                self.project,
                *args
            )
            if error:
                raise tornado.web.HTTPError(500, log_message="error creating project")
        else:
            category, error = yield self.application.structure.category_edit(
                self.category,
                *args
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
        categories, error = yield self.application.structure.get_project_categories(self.project)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        data = {
            'user': self.current_user,
            'project': self.project,
            'categories': categories
        }
        raise Return((data, None))

    @coroutine
    def get_edit(self):

        data = {
            'user': self.current_user,
            'project': self.project,
            'form': ProjectForm(self, **self.project),
            'render_control': render_control,
            'render_label': render_label
        }
        raise Return((data, None))

    @coroutine
    def post_general(self, submit):

        url = self.reverse_url("project_settings", self.project['name'], 'general')

        if submit == 'category_add':
            # add category

            category_name = self.get_argument('category_name', None)
            bidirectional = bool(self.get_argument('bidirectional', False))
            publish_to_admins = bool(self.get_argument('publish_to_admins', False))

            if category_name:

                category, error = yield self.application.structure.get_category_by_name(
                    self.project, category_name
                )

                if not category:
                    # create new category with unique name
                    res, error = yield self.application.structure.category_create(
                        self.project,
                        category_name,
                        bidirectional,
                        publish_to_admins
                    )
                    if error:
                        raise tornado.web.HTTPError(500, log_message=str(error))

        elif submit == 'category_del':
            # delete category
            category_name = self.get_argument('category_name', None)
            if category_name:
                res, error = yield self.application.structure.category_delete(
                    self.project, category_name
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))

        elif submit == 'regenerate_secret':
            # regenerate public and secret key
            res, error = yield self.application.structure.regenerate_project_secret_key(self.project)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

        self.redirect(url)

    @coroutine
    def post_edit(self, submit):

        #url = self.reverse_url("project_settings", self.project['name'], 'edit')

        if submit == 'project_del':
            # completely remove project
            confirm = self.get_argument('confirm', None)
            if confirm == self.project['name']:
                res, error = yield self.application.structure.project_delete(self.project)
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.redirect(self.reverse_url("main"))
                return

        elif submit == 'project_edit':
            # edit project
            form = ProjectForm(self)
            if not form.validate():
                self.render(
                    'project/settings_edit.html', project=self.project, form=form, render_control=render_control
                )
                return

            existing_project, error = yield self.application.structure.get_project_by_name(form.name.data)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

            if existing_project and existing_project['_id'] != self.project['_id']:
                form.name.errors.append('duplicate name')
                self.render(
                    'project/settings_edit.html', form=form, render_control=render_control
                )
                return

            res, error = yield self.application.structure.project_edit(
                self.project,
                form.name.data,
                form.display_name.data,
                '',
                form.auth_address.data,
                form.max_auth_attempts.data,
                form.back_off_interval.data,
                form.back_off_max_timeout.data
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

    def on_message_published(self, message):
        actual_message = message[1]
        if six.PY3:
            actual_message = actual_message.decode()
        self.send(actual_message)

    @coroutine
    def subscribe(self):

        projects, error = yield self.application.structure.project_list()
        self.projects = [x['_id'] for x in projects]
        self.uid = uuid.uuid4().hex
        self.connections = self.application.admin_connections

        context = zmq.Context()
        subscribe_socket = context.socket(zmq.SUB)

        if self.application.zmq_pub_sub_proxy:
            subscribe_socket.connect(self.application.zmq_xpub)
        else:
            for address in self.application.zmq_sub_address:
                subscribe_socket.connect(address)

        self.connections[self.uid] = self

        subscribe_socket.setsockopt_string(
            zmq.SUBSCRIBE, six.u(ADMIN_CHANNEL)
        )

        self.subscribe_stream = ZMQStream(subscribe_socket)
        self.subscribe_stream.on_recv(self.on_message_published)

        logger.info('admin connected')

    def unsubscribe(self):
        if not hasattr(self, 'uid'):
            return
        for project_id in self.projects:
            if not project_id in self.connections:
                continue
            try:
                del self.connections[project_id][self.uid]
            except KeyError:
                pass
            if not self.connections[project_id]:
                del self.connections[project_id]

        self.subscribe_stream.on_recv(None)
        self.subscribe_stream.close()
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