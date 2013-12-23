# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import six
import uuid
import tornado.web
import tornado.escape
import tornado.auth
import tornado.httpclient
import tornado.gen
from tornado.gen import coroutine, Return
from tornado.web import decode_signed_value
from tornado.escape import json_encode, json_decode
from sockjs.tornado import SockJSConnection

from centrifuge.log import logger
from centrifuge.handlers import BaseHandler
from centrifuge.forms import ProjectForm, NamespaceForm


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
        """
        user = self.current_user.decode()

        projects, error = yield self.application.structure.project_list()
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))

        context = {
            'js_data': tornado.escape.json_encode({
                'current_user': user,
                'socket_url': '/socket',
                'projects': projects
            }),
            'node_count': len(self.application.nodes) + 1,
            'pubsub': getattr(self.application.pubsub, 'NAME', 'unknown'),
            'structure': getattr(self.application.structure.storage, 'NAME', 'unknown'),
            'state': getattr(self.application.state, 'NAME', 'unknown')
        }
        if self.application.state.fake:
            context['state'] = 'Not configured'
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


class ProjectSettingsHandler(BaseHandler):
    """
    Edit project setting.
    """
    @coroutine
    def get_project(self, project_id):
        project, error = yield self.application.structure.get_project_by_id(project_id)
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

        if submit != 'regenerate_secret':
            raise tornado.web.HTTPError(400)

        confirm = self.get_argument('confirm', None)
        if confirm == self.project['name']:
            # regenerate project secret key
            res, error = yield self.application.structure.regenerate_project_secret_key(self.project)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))

        self.redirect(self.reverse_url("project_settings", self.project['_id'], 'general'))

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
            else:
                self.redirect(self.reverse_url("project_settings", self.project['_id'], "edit"))

        else:
            # edit project
            params = params_from_request(self.request)
            result, error = yield self.application.process_project_edit(self.project, params, error_form=True)
            if error and isinstance(error, six.string_types):
                # server error
                raise tornado.web.HTTPError(500)
            elif error:
                # error is form with errors in this case
                self.render(
                    'project/settings_edit.html', project=self.project,
                    form=error, render_control=render_control, render_label=render_label
                )
            else:
                self.redirect(self.reverse_url("project_settings", self.project['_id'], "edit"))

    @coroutine
    def get_actions(self):
        data, error = yield self.get_general()
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

        if section == 'general':
            template_name = 'project/settings_general.html'
            func = self.get_general

        elif section == 'edit':
            template_name = 'project/settings_edit.html'
            func = self.get_edit

        elif section == 'actions':
            template_name = 'project/settings_actions.html'
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

        if section == 'general':
            yield self.post_general(submit)

        elif section == 'edit':
            yield self.post_edit(submit)

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
                    namespace_id
                )
                if error:
                    raise tornado.web.HTTPError(500, log_message=str(error))
                self.redirect(
                    self.reverse_url("project_settings", self.project['_id'], 'general')
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
                    self.project, params, error_form=True
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
                self.redirect(self.reverse_url("project_settings", self.project['_id'], 'general'))


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
