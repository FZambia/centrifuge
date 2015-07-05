# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import six
import uuid
import functools
import tornado.web
import tornado.escape
import tornado.auth
import tornado.httpclient
import tornado.gen
from tornado.gen import coroutine
from tornado.web import decode_signed_value
from tornado.websocket import WebSocketHandler

import centrifuge
from centrifuge.log import logger
from centrifuge.utils import json_encode, json_decode
from centrifuge.handlers import BaseHandler


def authenticated(method):
    """
    Decorate methods with this to require that the user be logged in.
    As we serve single page app we use our own authenticated decorator
    to just return 401 response code
    """
    @functools.wraps(method)
    def wrapper(self, *args, **kwargs):
        if not self.current_user:
            raise tornado.web.HTTPError(401)
        return method(self, *args, **kwargs)
    return wrapper


class WebBaseHandler(BaseHandler):

    def get_current_user(self):
        if not self.opts.get("password"):
            return "authorized"
        auth_header = self.request.headers.get(
            "Authorization", "").split(" ")[-1]
        return decode_signed_value(
            self.application.settings['cookie_secret'],
            'token',
            auth_header
        )


class AuthHandler(BaseHandler):

    def post(self):
        password = self.get_argument("password", None)
        if password and password == self.opts.get("password"):
            token = self.create_signed_value("token", "authorized")
            self.set_header("Content-Type", "application/json")
            self.finish(json_encode({
                "token": token.decode('utf-8')
            }))
        else:
            raise tornado.web.HTTPError(400)


def params_from_request(request):
    return dict(
        (
            k,
            ''.join([x.decode('utf-8') for x in v])
        ) for k, v in six.iteritems(request.arguments)
    )


class InfoHandler(WebBaseHandler):

    @authenticated
    def get(self):
        config = self.application.settings.get('config', {})
        metrics_interval = config.get('metrics', {}).get(
            'interval', self.application.METRICS_EXPORT_INTERVAL)*1000
        context = {
            'structure':  self.application.structure,
            'metrics_interval': metrics_interval,
            'version': centrifuge.__version__,
            'nodes': self.application.nodes,
            'engine': getattr(self.application.engine, 'NAME', 'unknown'),
            'node_name': self.application.name
        }
        self.set_header("Content-Type", "application/json")
        self.finish(json_encode(context))


class ActionHandler(WebBaseHandler):

    @authenticated
    @coroutine
    def post(self):
        result, error = {}, None
        params = params_from_request(self.request)
        project = params.pop('project')
        method = params.pop('method')
        data = params.get('data')
        if data is not None:
            try:
                data = json_decode(data)
            except Exception as e:
                logger.error(e)
            else:
                params["data"] = data

        project = self.application.get_project(project)
        if not project:
            error = self.application.PROJECT_NOT_FOUND
        else:
            result, error = yield self.application.process_call(project, method, params)

        self.set_header("Content-Type", "application/json")
        self.finish(json_encode({
            "body": result,
            "error": error
        }))


class AdminWebSocketHandler(WebSocketHandler):

    def __init__(self, *args, **kwargs):
        super(AdminWebSocketHandler, self).__init__(*args, **kwargs)
        self.uid = None

    @coroutine
    def subscribe(self):
        self.uid = uuid.uuid4().hex
        self.application.add_admin_connection(self.uid, self)
        logger.debug('admin subscribed')

    def unsubscribe(self):
        if not self.uid:
            return
        self.application.remove_admin_connection(self.uid)
        logger.debug('admin unsubscribed')

    def open(self):
        logger.info('admin connected')

    def on_message(self, message):
        """
        The only method supported at moment - auth - used to
        authorize websocket connection.
        """
        try:
            data = json_decode(message)
        except ValueError:
            self.close()
            return

        try:
            method = data["method"]
            params = data["params"]
        except (TypeError, KeyError):
            self.close()
            return

        if method == "auth":
            try:
                token = params["token"]
            except (KeyError, TypeError):
                self.close()
                return
            else:
                user = decode_signed_value(
                    self.application.settings['cookie_secret'], 'token', token
                )
                if user:
                    self.subscribe()
                    self.send(json_encode({
                        "method": "auth",
                        "body": True
                    }))
                else:
                    self.send(json_encode({
                        "method": "auth",
                        "body": False
                    }))
                    self.close()
                    return
        else:
            self.close()
            return

    def on_close(self):
        self.unsubscribe()
        logger.info("admin disconnected")

    send = WebSocketHandler.write_message
