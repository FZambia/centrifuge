# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import tornado.web
from tornado.escape import json_encode
from tornado.gen import coroutine, Return
from sockjs.tornado import SockJSConnection

from jsonschema import validate, ValidationError

from . import auth
from .log import logger
from .response import Response
from .client import Client
from .schema import req_schema, server_api_schema, owner_api_methods


class BaseHandler(tornado.web.RequestHandler):

    def get_current_user(self):
        user = self.get_secure_cookie("user")
        if not user:
            return None
        return user

    def json_response(self, to_return):
        """
        Finish asynchronous request and return JSON response.
        """
        self.set_header('Content-Type', 'application/json; charset=utf-8')
        self.finish(tornado.escape.json_encode(to_return))

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
    def post(self, project_id):
        """
        Handle API HTTP requests.
        """
        if not self.request.body:
            raise tornado.web.HTTPError(400, log_message="empty request")

        sign = self.get_argument('sign', None)

        if not sign:
            raise tornado.web.HTTPError(400, log_message="no data sign")

        encoded_data = self.get_argument('data', None)
        if not encoded_data:
            raise tornado.web.HTTPError(400, log_message="no data")

        is_owner_request = False

        if project_id == self.application.MAGIC_PROJECT_ID:
            # API request aims to be from superuser
            is_owner_request = True

        if is_owner_request:
            # use api secret key from configuration to check sign
            secret = self.application.settings["config"].get("api_secret")
            if not secret:
                raise tornado.web.HTTPError(501, log_message="no api_secret in configuration file")
            project = None

        else:
            project, error = yield self.application.structure.get_project_by_id(project_id)
            if error:
                raise tornado.web.HTTPError(500, log_message=str(error))
            if not project:
                raise tornado.web.HTTPError(404, log_message="project not found")

            # use project secret key to validate sign
            secret = project['secret_key']

        is_valid = auth.check_sign(
            secret, project_id, encoded_data, sign
        )

        if not is_valid:
            raise tornado.web.HTTPError(401, log_message="unauthorized")

        data = auth.decode_data(encoded_data)
        if not data:
            raise tornado.web.HTTPError(400, log_message="malformed data")

        response = Response()

        try:
            validate(data, req_schema)
        except ValidationError as e:
            response.error = str(e)
        else:
            req_id = data.get("uid", None)
            method = data.get("method")
            params = data.get("params")

            response.uid = req_id
            response.method = method

            schema = server_api_schema

            if is_owner_request and self.application.MAGIC_PROJECT_PARAM in params:

                project_id = params[self.application.MAGIC_PROJECT_PARAM]

                project, error = yield self.application.structure.get_project_by_id(
                    project_id
                )
                if error:
                    logger.error(error)
                    response.error = self.application.INTERNAL_SERVER_ERROR
                if not project:
                    response.error = self.application.PROJECT_NOT_FOUND

            try:
                params.pop(self.application.MAGIC_PROJECT_PARAM)
            except KeyError:
                pass

            if not is_owner_request and method in owner_api_methods:
                response.error = self.application.PERMISSION_DENIED

            if not response.error:
                if method not in schema:
                    response.error = self.application.METHOD_NOT_FOUND
                else:
                    try:
                        validate(params, schema[method])
                    except ValidationError as e:
                        response.error = str(e)
                    else:
                        result, error = yield self.application.process_call(
                            project, method, params
                        )
                        response.body = result
                        response.error = error

        self.json_response(response.as_message())


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
