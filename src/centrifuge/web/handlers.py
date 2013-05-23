# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import time
import uuid
import logging
import tornado.web
import tornado.escape
import tornado.auth
import tornado.httpclient
import tornado.gen
from tornado.gen import Task, coroutine, Return
from sockjs.tornado import SockJSConnection

import zmq
from zmq.eventloop.zmqstream import ZMQStream

from .. import auth
from ..handlers import storage, BaseHandler, NAME_RE
from ..rpc import create_project_channel_name, CHANNEL_DATA_SEPARATOR


class GoogleAuthHandler(BaseHandler, tornado.auth.GoogleMixin):

    @tornado.web.asynchronous
    def get(self):
        if self.get_argument("openid.mode", None):
            self.get_authenticated_user(self.async_callback(self._on_auth))
            return
        self.authenticate_redirect()

    @coroutine
    def _on_auth(self, user):
        if not user:
            raise tornado.web.HTTPError(500, "Google auth failed")

        user_data, error = yield storage.get_or_create_user(
            self.db,
            user['email']
        )
        if error:
            raise tornado.web.HTTPError(500, "Auth failed")
        self.set_secure_cookie("user", tornado.escape.json_encode(user_data))
        self.redirect(self.reverse_url("main"))


class GithubAuthHandler(BaseHandler, auth.GithubMixin):

    x_site_token = 'centrifuge'

    @tornado.web.asynchronous
    def get(self):
        redirect_uri = "{0}://{1}{2}".format(
            self.request.protocol,
            self.request.host,
            self.reverse_url("auth_github")
        )
        params = {
            'redirect_uri': redirect_uri,
            'client_id':    self.opts['github_client_id'],
            'state':        self.x_site_token
        }

        code = self.get_argument('code', None)

        # Seek the authorization
        if code:
            # For security reason, the state value (cross-site token) will be
            # retrieved from the query string.
            params.update({
                'client_secret': self.opts['github_client_secret'],
                'success_callback': self._on_auth,
                'error_callback': self._on_error,
                'code':  code,
                'state': self.get_argument('state', None)
            })
            self.get_authenticated_user(**params)
            return

        # Redirect for user authentication
        self.get_authenticated_user(**params)

    @coroutine
    def _on_auth(self, user, access_token=None):
        if not user:
            raise tornado.web.HTTPError(500, "Github auth failed")
        user_data, error = yield storage.get_or_create_user(
            self.db,
            user['email']
        )
        if error:
            raise tornado.web.HTTPError(500, "Auth failed")
        self.set_secure_cookie("user", tornado.escape.json_encode(user_data))
        self.redirect(self.reverse_url("main"))

    def _on_error(self, code, body=None, error=None):
        if body:
            logging.error(body)
        if error:
            logging.error(error)
        raise tornado.web.HTTPError(500, "Github auth failed")


class LogoutHandler(BaseHandler):

    def get(self):
        self.clear_cookie("user")
        self.redirect(self.reverse_url("main"))


class AuthHandler(BaseHandler):

    def get(self):
        self.render('index.html')


class MainHandler(BaseHandler):

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @coroutine
    def get(self):
        """
        Render main template with additional data.
        Here we need information about categories and sources.
        Also information about watching and marked objects.
        """
        user = self.current_user

        projects, error = yield storage.get_user_projects(self.db, user)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        project_categories, error = yield storage.get_categories_for_projects(
            self.db,
            projects
        )
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        timestamp = str(int(time.time()))
        projects = list(projects)
        auth_token = auth.create_admin_token(
            self.settings['cookie_secret'],
            timestamp,
            user['_id'],
            (x.get("_id") for x in projects)
        )

        transports = self.opts.get(
            'sockjs_transports',
            ["websocket", "xhr-streaming", "iframe-eventsource"]
        )

        context = {
            'js_data': tornado.escape.json_encode({
                'current_user': user,
                'transports': transports,
                'socket_url': '/socket/',
                'auth_timestamp': timestamp,
                'auth_token': auth_token,
                'auth_user_id': user['_id'],
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

    @tornado.web.asynchronous
    @coroutine
    def post(self):
        user = self.current_user
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

        existing_project, error = yield storage.get_project_by_name(
            self.db,
            name
        )
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

        project, error = yield storage.project_create(
            self.db,
            user,
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

        readonly = False
        project_key, error = yield storage.add_user_into_project(
            self.db, user, project, readonly
        )
        if error:
            raise tornado.web.HTTPError(500, log_message="error creating project key")

        self.redirect(self.reverse_url('main'))


class ProjectSettingsHandler(BaseHandler):
    """
    Edit project setting.
    This part of application requires more careful implementation.
    """
    @coroutine
    def get_project_essentials(self, project_name):
        user = self.current_user

        project, error = yield storage.get_project_by_name(
            self.db, project_name
        )
        if not project:
            raise tornado.web.HTTPError(404)

        project_key, error = yield storage.get_user_project_key(
            self.db, user, project
        )
        if not project_key:
            raise tornado.web.HTTPError(403)

        is_owner = user['_id'] == project['owner']

        raise Return(((project, project_key, is_owner), None))

    @coroutine
    def get_general(self):
        categories, error = yield storage.get_project_categories(
            self.db, self.project
        )
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        data = {
            'user': self.current_user,
            'project': self.project,
            'project_key': self.project_key,
            'categories': categories,
            'is_owner': self.is_owner
        }
        raise Return((data, None))

    @coroutine
    def get_users(self):
        project_users = None
        if self.is_owner:
            project_users, error = yield storage.get_project_users(
                self.db, self.project
            )
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

        data = {
            'user': self.current_user,
            'project': self.project,
            'project_users': project_users,
            'project_key': self.project_key,
            'is_owner': self.is_owner
        }
        raise Return((data, None))

    @coroutine
    def get_edit(self):

        data = {
            'user': self.current_user,
            'project': self.project,
            'is_owner': self.is_owner
        }
        raise Return((data, None))

    @coroutine
    def post_general(self, submit):

        url = self.reverse_url("project_settings", self.project['name'], 'general')

        if submit == 'category_add':
            # add category
            if not self.is_owner:
                raise tornado.web.HTTPError(403)

            category_name = self.get_argument('category_name', None)
            bidirectional = bool(self.get_argument('bidirectional', False))
            publish_to_admins = bool(self.get_argument('publish_to_admins', False))

            if category_name:

                category, error = yield storage.get_project_category(
                    self.db, self.project, category_name
                )

                if not category:
                    # create new category with unique name
                    res, error = yield storage.category_create(
                        self.db,
                        self.project,
                        category_name,
                        bidirectional,
                        publish_to_admins
                    )
                    if error:
                        raise tornado.web.HTTPError(500, log_message=str(error))

        elif submit == 'category_del':
            # delete category
            if not self.is_owner:
                raise tornado.web.HTTPError(403)
            category_name = self.get_argument('category_name', None)
            if category_name:
                res, error = yield storage.category_delete(
                    self.db, self.project, category_name
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))

        elif submit == 'regenerate_secret':
            # regenerate public and secret key
            res, error = yield storage.regenerate_secret_key(
                self.db, self.user, self.project
            )
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

        self.redirect(url)

    @coroutine
    def post_users(self, submit):
        """
        pass
        """
        url = self.reverse_url("project_settings", self.project['name'], 'users')

        if submit == 'user_add':
            if not self.is_owner:
                raise tornado.web.HTTPError(403)

            email = self.get_argument('email', None)
            readonly = bool(
                self.get_argument('readonly', False)
            )
            user_to_add, error = yield storage.get_user_by_email(self.db, email)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

            if user_to_add and user_to_add['email'] != self.user['email']:
                res, error = yield storage.add_user_into_project(
                    self.db, user_to_add,
                    self.project,
                    readonly
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))

        elif submit == 'user_del':

            if not self.is_owner:
                raise tornado.web.HTTPError(403)

            email = self.get_argument('email', None)
            user_to_delete, error = yield storage.get_user_by_email(
                self.db, email
            )
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

            if user_to_delete and user_to_delete['email'] != self.user['email']:
                res, error = yield storage.del_user_from_project(
                    self.db, user_to_delete, self.project
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))

        self.redirect(url)

    @coroutine
    def post_edit(self, submit):

        url = self.reverse_url("project_settings", self.project['name'], 'edit')

        if not self.is_owner:
            raise tornado.web.HTTPError(403)

        if submit == 'project_del':
            # completely remove project
            confirm = self.get_argument('confirm', None)
            if confirm == self.project['name']:
                res, error = yield storage.project_delete(
                    self.db, self.project
                )
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

                res, error = yield storage.project_edit(
                    self.db, self.project, name, display_name,
                    description, validate_url, auth_attempts,
                    back_off_interval, back_off_max_timeout
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.redirect(self.reverse_url("project_settings", name, "edit"))
                return

        self.redirect(url)

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @coroutine
    def get(self, project_name, section):

        (self.project, self.project_key, self.is_owner), error = yield self.get_project_essentials(
            project_name
        )

        if section == 'general':
            template_name = 'project/settings_general.html'
            func = self.get_general

        elif section == 'users':
            template_name = 'project/settings_users.html'
            func = self.get_users

        elif section == 'edit':
            template_name = 'project/settings_edit.html'
            func = self.get_edit

        else:
            raise tornado.web.HTTPError(404)

        data, error = yield func()

        self.render(template_name, **data)

    @tornado.web.authenticated
    @tornado.web.asynchronous
    @coroutine
    def post(self, project_name, section):
        self.user = self.current_user

        (self.project, self.project_key, self.is_owner), error = yield self.get_project_essentials(
            project_name
        )

        submit = self.get_argument('submit', None)

        if section == 'general':
            yield Task(self.post_general, submit)

        elif section == 'users':
            yield Task(self.post_users, submit)

        elif section == 'edit':
            yield Task(self.post_edit, submit)

        else:
            raise tornado.web.HTTPError(404)


class AdminSocketHandler(SockJSConnection):

    def on_message(self, message):

        if self.is_closed:
            return

        data = tornado.escape.json_decode(message)

        auth_token = data.get("auth_token", None)
        auth_timestamp = data.get("auth_timestamp", None)
        auth_user_id = data.get("auth_user_id", '')
        projects = data.get("projects", None)

        if not auth_token or not auth_timestamp:
            self.close()

        try:
            auth_timestamp = int(auth_timestamp)
        except ValueError:
            self.close()

        if abs(time.time() - auth_timestamp) > self.opts.get("max_token_delay", 5):
            self.close()

        token = auth.create_admin_token(
            self.application.settings['cookie_secret'],
            auth_timestamp,
            auth_user_id,
            projects
        )
        if token != auth_token:
            self.close()

        self.projects = projects
        self.user_id = auth_user_id
        self.is_authenticated = True
        self.uid = uuid.uuid4().hex
        self.connections = self.application.admin_connections

        self.subscribe()

        if self.session:
            if self.session.transport_name != 'websocket':
                self.session.start_heartbeat()
        else:
            self.close()

    def on_message_published(self, message):
        self.send(message[0].split(CHANNEL_DATA_SEPARATOR, 1)[1])

    def subscribe(self):

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
            if self.user_id not in self.connections[project_id]:
                self.connections[project_id][self.user_id] = {}
            self.connections[project_id][self.user_id][self.uid] = self

            channel_to_subscribe = create_project_channel_name(project_id)
            subscribe_socket.setsockopt(zmq.SUBSCRIBE, channel_to_subscribe)

        self.subscribe_stream = ZMQStream(subscribe_socket)
        self.subscribe_stream.on_recv(self.on_message_published)

    def unsubscribe(self):
        for project_id in self.projects:
            if not project_id in self.connections:
                continue
            if not self.user_id in self.connections[project_id]:
                continue
            try:
                del self.connections[project_id][self.user_id][self.uid]
            except KeyError:
                pass
            if not self.connections[project_id][self.user_id]:
                del self.connections[project_id][self.user_id]

        self.subscribe_stream.on_recv(None)
        self.subscribe_stream.close()

    def on_open(self, info):
        logging.info('admin connected')
        self.is_authenticated = False
        self.opts = self.application.settings['options']

    def on_close(self):
        logging.info('admin disconnected')
        self.unsubscribe()


class Http404Handler(BaseHandler):

    def get(self):
        self.render("http404.html")

