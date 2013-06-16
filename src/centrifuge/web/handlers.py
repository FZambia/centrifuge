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
from tornado.websocket import WebSocketHandler

import six

import zmq
from zmq.eventloop.zmqstream import ZMQStream

from ..log import logger
from ..handlers import state, BaseHandler, NAME_RE
from ..rpc import create_project_channel_name, CHANNEL_DATA_SEPARATOR


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

        projects, error = yield state.project_list()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        project_categories, error = yield state.get_categories_for_projects()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        context = {
            'js_data': tornado.escape.json_encode({
                'current_user': user,
                'socket_url': self.reverse_url("admin_connection"),
                'projects': projects,
                'categories': project_categories
            })
        }
        self.render("main.html", **context)


class ProjectCreateHandler(BaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render(
            'project/create.html', form_data={}
        )

    @tornado.web.authenticated
    @coroutine
    def post(self):
        validation_error = False
        name = self.get_argument("name", None)
        display_name = self.get_argument("display_name", "")
        description = self.get_argument("description", "")
        validate_url = self.get_argument("validate_url", "")
        auth_attempts = self.get_argument("auth_attempts", None)
        back_off_interval = self.get_argument("back_off_interval", None)
        back_off_max_timeout = self.get_argument("back_off_max_timeout", None)

        if name:
            name = name.lower()

        if auth_attempts:
            try:
                auth_attempts = abs(int(float(auth_attempts)))
            except ValueError:
                auth_attempts = None

        if back_off_interval:
            try:
                back_off_interval = abs(int(float(back_off_interval)))
            except ValueError:
                back_off_interval = None

        if back_off_max_timeout:
            try:
                back_off_max_timeout = abs(int(float(back_off_max_timeout)))
            except ValueError:
                back_off_max_timeout = None

        if not name or not NAME_RE.search(name):
            validation_error = True

        existing_project, error = yield state.get_project_by_name(name)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if existing_project:
            validation_error = True

        if validation_error:
            form_data = {
                'name': name,
                'display_name': display_name,
                'validate_url': validate_url,
                'description': description,
                'auth_attempts': auth_attempts,
                'back_off_interval': back_off_interval,
                'back_off_max_timeout': back_off_max_timeout
            }
            self.render(
                'project/create.html', form_data=form_data
            )
            return

        if not display_name:
            display_name = name

        project, error = yield state.project_create(
            name,
            display_name,
            description,
            validate_url,
            auth_attempts,
            back_off_interval,
            back_off_max_timeout
        )
        if error:
            raise tornado.web.HTTPError(500, log_message="error creating project")

        self.redirect(self.reverse_url('main'))


class ProjectSettingsHandler(BaseHandler):
    """
    Edit project setting.
    This part of application requires more careful implementation.
    """
    @coroutine
    def get_project(self, project_name):

        project, error = yield state.get_project_by_name(project_name)
        if not project:
            raise tornado.web.HTTPError(404)

        raise Return((project, None))

    @coroutine
    def get_general(self):
        categories, error = yield state.get_project_categories(self.project)
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

                category, error = yield state.get_category_by_name(
                    self.project, category_name
                )

                if not category:
                    # create new category with unique name
                    res, error = yield state.category_create(
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
                res, error = yield state.category_delete(
                    self.project, category_name
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))

        elif submit == 'regenerate_secret':
            # regenerate public and secret key
            res, error = yield state.regenerate_project_secret_key(self.project)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

        self.redirect(url)

    @coroutine
    def post_edit(self, submit):

        url = self.reverse_url("project_settings", self.project['name'], 'edit')

        if submit == 'project_del':
            # completely remove project
            confirm = self.get_argument('confirm', None)
            if confirm == self.project['name']:
                res, error = yield state.project_delete(self.project)
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.redirect(self.reverse_url("main"))
                return

        elif submit == 'project_edit':
            # edit project
            name = self.get_argument('name', None)
            if name and NAME_RE.search(name):
                display_name = self.get_argument('display_name', None)
                description = self.get_argument('description', "")
                validate_url = self.get_argument('validate_url', "")
                auth_attempts = self.get_argument("auth_attempts", None)
                back_off_interval = self.get_argument(
                    "back_off_interval", None
                )
                back_off_max_timeout = self.get_argument(
                    'back_off_max_timeout', None
                )

                if name:
                    name = name.lower()

                if auth_attempts:
                    try:
                        auth_attempts = abs(int(float(auth_attempts)))
                    except ValueError:
                        auth_attempts = None

                if back_off_interval:
                    try:
                        back_off_interval = abs(int(float(back_off_interval)))
                    except ValueError:
                        back_off_interval = None

                if back_off_max_timeout:
                    try:
                        back_off_max_timeout = abs(int(float(back_off_max_timeout)))
                    except ValueError:
                        back_off_max_timeout = None

                if not display_name:
                    display_name = name

                res, error = yield state.project_edit(
                    self.project, name, display_name,
                    description, validate_url, auth_attempts,
                    back_off_interval, back_off_max_timeout
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.redirect(self.reverse_url("project_settings", name, "edit"))
                return

        self.redirect(url)

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


class AdminSocketHandler(BaseHandler, WebSocketHandler):

    def on_message_published(self, message):
        actual_message = message[0]
        if six.PY3:
            actual_message = actual_message.decode()
        self.write_message(
            actual_message.split(CHANNEL_DATA_SEPARATOR, 1)[1]
        )

    @coroutine
    def subscribe(self):

        projects, error = yield state.project_list()
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

        for project_id in self.projects:
            if project_id not in self.connections:
                self.connections[project_id] = {}
            self.connections[project_id][self.uid] = self

            channel_to_subscribe = create_project_channel_name(project_id)
            subscribe_socket.setsockopt_string(
                zmq.SUBSCRIBE, six.u(channel_to_subscribe)
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

    def open(self):
        if not self.current_user:
            self.close()
        else:
            self.subscribe()

    def on_close(self):
        self.unsubscribe()


class Http404Handler(BaseHandler):

    def get(self):
        self.render("http404.html")

