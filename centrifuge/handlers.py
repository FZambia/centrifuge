# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import tornado.web
from tornado.gen import coroutine, Return
from sockjs.tornado import SockJSConnection

from centrifuge import auth
from centrifuge.log import logger
from centrifuge.client import Client
from centrifuge.utils import json_decode


class BaseHandler(tornado.web.RequestHandler):

    def json_response(self, to_return):
        """
        Finish asynchronous request and return JSON response.
        """
        self.set_header('Content-Type', 'application/json; charset=utf-8')
        self.finish(to_return)

    @property
    def opts(self):
        return self.settings.get('config', {})


class ApiHandler(BaseHandler):
    """
    Listen for incoming POST request, authorize it and in case off
    successful authorization process requested action for project.
    """
    def check_xsrf_cookie(self):
        """
        No need in CSRF protection here.
        """
        pass

    @coroutine
    def post(self, project_key):
        """
        Handle API HTTP requests.
        """
        timer = None
        if self.application.collector:
            timer = self.application.collector.get_timer('api_time')

        if not self.request.body:
            raise tornado.web.HTTPError(400, log_message="empty request")

        if self.request.headers.get("Content-Type", "").startswith("application/json"):
            # handle JSON requests if corresponding Content-Type specified
            encoded_data = self.request.body
            sign = self.request.headers.get("X-API-Sign")
        else:
            # handle application/x-www-form-urlencoded request
            sign = self.get_argument('sign', None)
            encoded_data = self.get_argument('data', None)

        if not sign:
            raise tornado.web.HTTPError(400, log_message="no data sign")

        if not encoded_data:
            raise tornado.web.HTTPError(400, log_message="no data")

        project = self.application.get_project(project_key)
        if not project:
            raise tornado.web.HTTPError(404, log_message="project not found")

        # use project secret to validate sign
        secret = project['secret']

        is_valid = auth.check_sign(
            secret, project_key, encoded_data, sign
        )

        if not is_valid:
            raise tornado.web.HTTPError(401, log_message="unauthorized")

        try:
            data = json_decode(encoded_data)
        except Exception as err:
            logger.debug(err)
            raise tornado.web.HTTPError(400, log_message="malformed data")

        multi_response, error = yield self.application.process_api_data(project, data)
        if error:
            raise tornado.web.HTTPError(400, log_message=error)

        if self.application.collector:
            self.application.collector.incr('api')
            timer.stop()

        self.json_response(multi_response.as_message())


class SockjsConnection(SockJSConnection):

    def on_open(self, info):
        if self.session:
            self.client = Client(self, info)
            if self.session.transport_name != 'rawwebsocket':
                self.session.start_heartbeat()
        else:
            self.close()

    @coroutine
    def on_message(self, message):
        yield self.client.message_received(message)
        raise Return((True, None))

    @coroutine
    def on_close(self):
        if hasattr(self, 'client'):
            yield self.client.close()
            del self.client
        raise Return((True, None))
