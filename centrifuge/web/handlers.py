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

from centrifuge.log import logger
from centrifuge.utils import json_encode, json_decode
from centrifuge.handlers import BaseHandler
from centrifuge.forms import ProjectForm, NamespaceForm


class LogoutHandler(BaseHandler):

    def get(self):
        self.clear_cookie("user")
        self.redirect(self.reverse_url("main"))


class AuthHandler(BaseHandler):

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


class MainHandler(BaseHandler):

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
            self.redirect(self.reverse_url('main'))


class ProjectDetailHandler(BaseHandler):

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
                self.redirect(self.reverse_url("main"))
            else:
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


class NamespaceFormHandler(BaseHandler):

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
                self.redirect(
                    self.reverse_url("project_detail", self.project['_id'], 'namespaces')
                )
            else:
                self.redirect(
                    self.reverse_url("namespace_edit", self.project['_id'], namespace_id)
                )
        else:
            params = params_from_request(self.request)

            if namespace_id:
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
                self.redirect(self.reverse_url("project_detail", self.project['_id'], 'namespaces'))


class AdminSocketHandler(SockJSConnection):

    @coroutine
    def subscribe(self):
        self.uid = uuid.uuid4().hex
        self.application.add_admin_connection(self.uid, self)
        logger.debug('admin connected')

    def unsubscribe(self):
        if not hasattr(self, 'uid'):
            return
        self.application.remove_admin_connection(self.uid)
        logger.debug('admin disconnected')

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


class StructureLoadHandler(BaseHandler):

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
