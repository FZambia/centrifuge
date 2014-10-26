# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import six
import uuid
import tornado.web
import tornado.escape
import tornado.auth
import tornado.httpclient
import tornado.gen
from tornado.gen import coroutine, Return
from tornado.web import decode_signed_value
from sockjs.tornado import SockJSConnection

import centrifuge
from centrifuge.log import logger
from centrifuge.utils import json_encode, json_decode
from centrifuge.handlers import BaseHandler
from centrifuge.forms import ProjectForm, NamespaceForm


flash_messages = {
    "project_create_success": "New project created",
    "project_update_success": "Project settings updated",
    "project_delete_success": "Project deleted",
    "project_delete_error": "Project not deleted",
    "project_secret_regenerate_success": "Project secret key regenerated",
    "project_secret_regenerate_error": "Project secret key not modified",
    "namespace_create_success": "New namespace created",
    "namespace_update_success": "Namespace settings updated",
    "namespace_delete_success": "Namespace deleted",
    "namespace_delete_error": "Namespace not deleted",
}


class WebBaseHandler(BaseHandler):

    FLASH_COOKIE_NAME = 'flash'

    def get_current_user(self):
        user = self.get_secure_cookie("user")
        if not user:
            return None
        return user

    def get_flash_message(self):
        """
        Returns the flash message.
        """
        cookie = self.get_secure_cookie(self.FLASH_COOKIE_NAME)
        if cookie:
            self.clear_cookie(self.FLASH_COOKIE_NAME)
            return json_decode(cookie)
        return None

    def set_flash_message(self, message, status='success'):
        """
        Stores a Flash object as a flash cookie under a given key.
        """
        flash = {
            'message': message,
            'status': status
        }
        self.set_secure_cookie(self.FLASH_COOKIE_NAME, json_encode(flash))


class LogoutHandler(WebBaseHandler):

    def get(self):
        self.clear_cookie("user")
        self.redirect(self.reverse_url("main"))


class AuthHandler(WebBaseHandler):

    def authorize(self):
        self.set_secure_cookie("user", "authorized")
        next_url = self.get_argument("next", None)
        if next_url:
            self.redirect(next_url)
        else:
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


class MainHandler(WebBaseHandler):

    @tornado.web.authenticated
    @coroutine
    def get(self):
        """
        Render main template with additional data.
        """
        user = self.current_user.decode()

        projects, error = yield self.application.structure.project_list()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        config = self.application.settings.get('config', {})
        metrics_interval = config.get('metrics', {}).get('interval', self.application.METRICS_EXPORT_INTERVAL)*1000

        context = {
            'js_data': tornado.escape.json_encode({
                'current_user': user,
                'socket_url': '/socket',
                'projects': projects,
                'metrics_interval': metrics_interval
            }),
            'centrifuge_version': centrifuge.__version__,
            'node_count': len(self.application.nodes) + 1,
            'engine': getattr(self.application.engine, 'NAME', 'unknown'),
            'structure': getattr(self.application.structure.storage, 'NAME', 'unknown')
        }
        self.render("main.html", **context)


def render_control(field):
    if field.type == 'BooleanField':
        return field()
    return field(class_="form-control")


def render_label(label):
    return label(class_="col-lg-2 control-label")


def params_from_request(request):
    return dict((k, ''.join([x.decode('utf-8') for x in v])) for k, v in six.iteritems(request.arguments))


class ProjectCreateHandler(WebBaseHandler):

    @tornado.web.authenticated
    def get(self):

        self.render(
            'project/create.html', form=ProjectForm(self),
            render_control=render_control, render_label=render_label
        )

    @tornado.web.authenticated
    @coroutine
    def post(self):

        params = params_from_request(self.request)
        result, error = yield self.application.process_project_create(None, params, error_form=True)

        if error and isinstance(error, six.string_types):
            # server error
            raise tornado.web.HTTPError(500)
        elif error:
            # error is form with errors in this case
            self.render(
                'project/create.html', form=error,
                render_control=render_control, render_label=render_label
            )
        else:
            self.set_flash_message(flash_messages["project_create_success"])
            self.redirect(self.reverse_url('main'))


class ProjectDetailHandler(WebBaseHandler):

    @coroutine
    def get_project(self, project_id):
        project, error = yield self.application.structure.get_project_by_id(project_id)
        if not project:
            raise tornado.web.HTTPError(404)
        raise Return((project, None))

    @coroutine
    def get_credentials(self):
        data = {
            'user': self.current_user,
            'project': self.project,
        }
        raise Return((data, None))

    @coroutine
    def get_namespaces(self):
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
    def post_credentials(self, submit):

        if submit != 'regenerate_secret':
            raise tornado.web.HTTPError(400)

        confirm = self.get_argument('confirm', None)
        if confirm == self.project['name']:
            # regenerate project secret key
            res, error = yield self.application.structure.regenerate_project_secret_key(self.project)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))
            self.set_flash_message(flash_messages["project_secret_regenerate_success"])
        else:
            self.set_flash_message(flash_messages["project_secret_regenerate_error"], status="danger")

        self.redirect(self.reverse_url("project_detail", self.project['_id'], 'credentials'))

    @coroutine
    def get_settings(self):
        data = {
            'user': self.current_user,
            'project': self.project,
            'form': ProjectForm(self, **self.project),
            'render_control': render_control,
            'render_label': render_label
        }
        raise Return((data, None))

    @coroutine
    def post_settings(self, submit):

        if submit == 'project_del':
            # completely remove project
            confirm = self.get_argument('confirm', None)
            if confirm == self.project['name']:
                res, error = yield self.application.structure.project_delete(self.project)
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.set_flash_message(flash_messages["project_delete_success"])
                self.redirect(self.reverse_url("main"))
            else:
                self.set_flash_message(flash_messages["project_delete_error"], status="danger")
                self.redirect(self.reverse_url("project_detail", self.project['_id'], "settings"))

        else:
            # edit project
            params = params_from_request(self.request)
            result, error = yield self.application.process_project_edit(
                self.project, params, error_form=True, patch=False
            )
            if error and isinstance(error, six.string_types):
                # server error
                raise tornado.web.HTTPError(500)
            elif error:
                # error is form with errors in this case
                self.render(
                    'project/detail_settings.html', project=self.project,
                    form=error, render_control=render_control, render_label=render_label
                )
            else:
                self.set_flash_message(flash_messages["project_update_success"])
                self.redirect(self.reverse_url("project_detail", self.project['_id'], "settings"))

    @coroutine
    def get_actions(self):
        data, error = yield self.get_credentials()
        raise Return((data, None))

    @coroutine
    def post_actions(self):
        params = params_from_request(self.request)
        method = params.pop('method')
        params.pop('_xsrf')
        data = params.get('data', None)
        if data is not None:
            try:
                data = json_decode(data)
            except Exception as e:
                logger.error(e)
            else:
                params["data"] = data

        result, error = yield self.application.process_call(self.project, method, params)

        self.set_header("Content-Type", "application/json")
        self.finish(json_encode({
            "body": result,
            "error": error
        }))

    @tornado.web.authenticated
    @coroutine
    def get(self, project_name, section):

        self.project, error = yield self.get_project(project_name)

        if section == 'credentials':
            template_name = 'project/detail_credentials.html'
            func = self.get_credentials

        elif section == 'settings':
            template_name = 'project/detail_settings.html'
            func = self.get_settings

        elif section == 'namespaces':
            template_name = 'project/detail_namespaces.html'
            func = self.get_namespaces

        elif section == 'actions':
            template_name = 'project/detail_actions.html'
            func = self.get_actions

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

        if section == 'credentials':
            yield self.post_credentials(submit)

        elif section == 'settings':
            yield self.post_settings(submit)

        elif section == 'actions':
            yield self.post_actions()

        else:
            raise tornado.web.HTTPError(404)


class NamespaceFormHandler(WebBaseHandler):

    @coroutine
    def get_project(self, project_id):
        project, error = yield self.application.structure.get_project_by_id(project_id)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if not project:
            raise tornado.web.HTTPError(404)
        raise Return((project, None))

    @coroutine
    def get_namespace(self, namespace_id):
        namespace, error = yield self.application.structure.get_namespace_by_id(
            namespace_id
        )
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if not namespace:
            raise tornado.web.HTTPError(404)
        raise Return((namespace, error))

    @tornado.web.authenticated
    @coroutine
    def get(self, project_id, namespace_id=None):

        self.project, error = yield self.get_project(project_id)

        if namespace_id:
            template_name = 'namespace/edit.html'
            self.namespace, error = yield self.get_namespace(namespace_id)
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
    def post(self, project_id, namespace_id=None):

        self.project, error = yield self.get_project(project_id)

        if namespace_id:
            self.namespace, error = yield self.get_namespace(namespace_id)

        submit = self.get_argument('submit', None)

        if submit == 'namespace_delete':
            if self.get_argument('confirm', None) == self.namespace["name"]:
                res, error = yield self.application.structure.namespace_delete(
                    self.namespace
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.set_flash_message(flash_messages["namespace_delete_success"])
                self.redirect(
                    self.reverse_url("project_detail", self.project['_id'], 'namespaces')
                )
            else:
                self.set_flash_message(flash_messages["namespace_delete_error"], status="danger")
                self.redirect(
                    self.reverse_url("namespace_edit", self.project['_id'], namespace_id)
                )
        else:
            params = params_from_request(self.request)

            is_editing = False

            if namespace_id:
                is_editing = True
                template_name = 'namespace/edit.html'
                params['_id'] = namespace_id
                result, error = yield self.application.process_namespace_edit(
                    self.project, params, error_form=True, patch=False
                )
            else:
                template_name = 'namespace/create.html'
                result, error = yield self.application.process_namespace_create(
                    self.project, params, error_form=True
                )

            if error and isinstance(error, six.string_types):
                # server error
                raise tornado.web.HTTPError(500)
            elif error:
                # error is form with errors in this case
                self.render(
                    template_name, form=error, project=self.project,
                    render_control=render_control, render_label=render_label
                )
            else:
                flash_key = "namespace_update_success" if is_editing else "namespace_create_success"
                self.set_flash_message(flash_messages[flash_key])
                self.redirect(self.reverse_url("project_detail", self.project['_id'], 'namespaces'))


class AdminSocketHandler(SockJSConnection):

    @coroutine
    def subscribe(self):
        self.uid = uuid.uuid4().hex
        self.application.add_admin_connection(self.uid, self)
        logger.info('admin connected')

    def unsubscribe(self):
        if not hasattr(self, 'uid'):
            return
        self.application.remove_admin_connection(self.uid)
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


class Http404Handler(WebBaseHandler):

    def get(self):
        self.render("http404.html")


class StructureDumpHandler(WebBaseHandler):

    @tornado.web.authenticated
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


class StructureLoadHandler(WebBaseHandler):

    @tornado.web.authenticated
    def get(self):
        self.render("loads.html")

    @tornado.web.authenticated
    @coroutine
    def post(self):
        json_data = self.get_argument("data")
        data = json_decode(json_data)
        res, err = yield self.application.structure.clear_structure()
        if err:
            raise tornado.web.HTTPError(500, log_message=str(err))

        for project in data.get("projects", []):
            res, err = yield self.application.structure.project_create(**project)
            if err:
                raise tornado.web.HTTPError(500, log_message=str(err))
            for namespace in data.get("namespaces", []):
                if namespace["project_id"] != project["_id"]:
                    continue
                res, err = yield self.application.structure.namespace_create(project, **namespace)
                if err:
                    raise tornado.web.HTTPError(500, log_message=str(err))

        self.redirect(self.reverse_url("main"))
