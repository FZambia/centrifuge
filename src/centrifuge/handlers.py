# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import re
import uuid
import six
import tornado.web
import time
import random
from tornado.ioloop import IOLoop
from tornado.escape import json_encode, json_decode
from tornado.gen import coroutine, Return, Task
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.websocket import WebSocketHandler
from sockjs.tornado import SockJSConnection

import zmq
from zmq.eventloop.zmqstream import ZMQStream
from jsonschema import validate, ValidationError

from .log import logger
from . import rpc
from . import auth
from .schema import req_schema, admin_params_schema, client_params_schema


state = None


# regex pattern to match project and category names
NAME_RE = re.compile('^[^_]+[A-z0-9]{2,}$')


@coroutine
def sleep(seconds):
    """
    Non-blocking sleep
    """
    yield Task(IOLoop.instance().add_timeout, time.time()+seconds)
    raise Return((True, None))


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
        return self.settings.get('options', {})


class RpcHandler(BaseHandler):
    """
    Listen for incoming POST request, authorize it and in case off
    successful authorization process requested action for project.
    """
    def check_xsrf_cookie(self):
        """
        We do not need xsrf protection here.
        """
        pass

    @tornado.web.asynchronous
    @coroutine
    def post(self, project_id):
        """
        Handle requests from clients.
        """
        if not self.request.body:
            raise tornado.web.HTTPError(400, log_message="empty request")

        auth_info, error = auth.extract_auth_info(self.request)
        if error:
            raise tornado.web.HTTPError(401, log_message=error)

        sign = auth_info['sign']

        project, error = yield state.get_project_by_id(project_id)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if not project:
            raise tornado.web.HTTPError(404, log_message="project not found")

        encoded_data = self.request.body
        if not encoded_data:
            raise tornado.web.HTTPError(400, log_message="no request body")

        result, error = yield state.check_auth(project, sign, encoded_data)
        if error:
            raise tornado.web.HTTPError(500, log_message=str(error))
        if not result:
            raise tornado.web.HTTPError(401, log_message="unauthorized")

        data = auth.decode_data(encoded_data)
        if not data:
            raise tornado.web.HTTPError(400, log_message="malformed data")

        context = {
            'id': None,
            'error': None,
            'result': None
        }

        try:
            validate(data, req_schema)
        except ValidationError as e:
            context['error'] = str(e)
        else:
            req_id = data.get("id", None)
            method = data.get("method")
            params = data.get("params")

            context['id'] = req_id

            if method not in admin_params_schema:
                context['error'] = "method not found"
            else:
                try:
                    validate(params, admin_params_schema[method])
                except ValidationError as e:
                    context['error'] = str(e)
                else:
                    result, error = yield rpc.process_call(
                        self.application, project, method, params
                    )

                    context['error'] = error
                    context['result'] = result

        self.json_response(context)


class Connection(object):
    """
    This is a base class describing a single connection of client from
    web browser.
    """
    # maximum auth validation requests before returning error to client
    MAX_AUTH_ATTEMPTS = 5

    # interval unit in milliseconds for back off
    BACK_OFF_INTERVAL = 100

    # maximum timeout between authorization attempts in back off
    BACK_OFF_MAX_TIMEOUT = 5000

    def close_connection(self):
        """
        General method for closing connection.
        """
        if isinstance(self, (SockJSConnection, WebSocketHandler)):
            self.close()

    def send_message(self, message):
        """
        Send message to client
        """
        if isinstance(self, SockJSConnection):
            self.send(message)
        elif isinstance(self, WebSocketHandler):
            self.write_message(message)

    def send_ack(self, msg_id=None, method=None, result=None, error=None):
        self.send_message(
            self.make_ack(
                msg_id=msg_id,
                method=method,
                result=result,
                error=error
            )
        )

    def make_ack(self, msg_id=None, method=None, result=None, error=None):

        to_return = {
            'ack': True,
            'id': msg_id,
            'method': method,
            'result': result,
            'error': error
        }
        return json_encode(to_return)

    @coroutine
    def handle_auth(self, params):

        if self.is_authenticated:
            raise Return((True, None))

        token = params["token"]
        user = params["user"]
        project_id = params['project_id']
        permissions = params["permissions"]

        project, error = yield state.get_project_by_id(project_id)
        if error:
            self.close_connection()
        if not project:
            raise Return((None, "project not found"))

        secret_key = project['secret_key']

        if token != auth.get_client_token(secret_key, project_id, user):
            raise Return((None, "invalid token"))

        if user and project.get('validate_url', None):

            http_client = AsyncHTTPClient()
            request = HTTPRequest(
                project['validate_url'],
                method="POST",
                body=json_encode({'user': user, 'permissions': permissions}),
                request_timeout=1
            )

            max_auth_attempts = project.get(
                'auth_attempts'
            ) or self.MAX_AUTH_ATTEMPTS

            back_off_interval = project.get(
                'back_off_interval'
            ) or self.BACK_OFF_INTERVAL

            back_off_max_timeout = project.get(
                'back_off_max_timeout'
            ) or self.BACK_OFF_MAX_TIMEOUT

            attempts = 0

            while attempts < max_auth_attempts:

                # get current timeout for project
                current_attempts = self.application.back_off.setdefault(project_id, 0)

                factor = random.randint(0, 2**current_attempts-1)
                timeout = factor*back_off_interval

                if timeout > back_off_max_timeout:
                    timeout = back_off_max_timeout

                # wait before next authorization request attempt
                yield sleep(float(timeout)/1000)

                try:
                    response = yield http_client.fetch(request)
                except BaseException:
                    # let it fail and try again after some timeout
                    # until we have auth attempts
                    pass
                else:
                    # reset back-off attempts
                    self.application.back_off[project_id] = 0

                    if response.code == 200:
                        self.is_authenticated = True
                        break
                    elif response.code == 403:
                        raise Return((None, "permission denied"))
                attempts += 1
                self.application.back_off[project_id] += 1
        else:
            self.is_authenticated = True

        if not self.is_authenticated:
            raise Return((None, "permission validation error"))

        categories, error = yield state.get_project_categories(project)
        if error:
            self.close_connection()

        self.categories = {}
        for category in categories:
            if not permissions or (permissions and category['name'] in permissions):
                self.categories[category['name']] = category

        self.uid = uuid.uuid4().hex
        self.project = project
        self.permissions = permissions
        self.user = user
        self.channels = {}
        self.start_heartbeat()

        # allow broadcast from client only into bidirectional categories
        self.bidirectional_categories = {}
        for category_name, category in six.iteritems(self.categories):
            if category.get('bidirectional', False):
                self.bidirectional_categories[category_name] = category

        context = zmq.Context()
        subscribe_socket = context.socket(zmq.SUB)

        if self.application.zmq_pub_sub_proxy:
            subscribe_socket.connect(self.application.zmq_xpub)
        else:
            for address in self.application.zmq_sub_address:
                subscribe_socket.connect(address)

        self.sub_stream = ZMQStream(subscribe_socket)
        self.sub_stream.on_recv(self.on_message_published)

        raise Return((True, None))

    @coroutine
    def handle_subscribe(self, params):
        """
        Subscribe authenticated connection on channels.
        """
        subscribe_to = params.get('to')

        if not subscribe_to:
            raise Return((True, None))

        project_id = self.project['_id']

        connections = self.application.connections

        if project_id not in connections:
            connections[project_id] = {}

        if self.user and self.user not in connections:
            connections[project_id][self.user] = {}

        if self.user:
            connections[project_id][self.user][self.uid] = self

        for category_name, channels in six.iteritems(subscribe_to):

            if category_name not in self.categories:
                # attempt to subscribe on not allowed category
                continue

            if not channels or not isinstance(channels, list):
                # attempt to subscribe without channels provided
                continue

            category_id = self.categories[category_name]['_id']

            allowed_channels = self.permissions.get(category_name) if self.permissions else []

            for channel in channels:

                if not isinstance(allowed_channels, list):
                    continue

                if allowed_channels and channel not in allowed_channels:
                    # attempt to subscribe on not allowed channel
                    continue

                channel_to_subscribe = rpc.create_channel_name(
                    project_id,
                    category_id,
                    channel
                )
                self.sub_stream.setsockopt_string(
                    zmq.SUBSCRIBE, six.u(channel_to_subscribe)
                )

                if category_name not in self.channels:
                    self.channels[category_name] = {}
                self.channels[category_name][channel_to_subscribe] = True

        raise Return((True, None))

    @coroutine
    def handle_unsubscribe(self, params):
        unsubscribe_from = params.get('from')

        if not unsubscribe_from:
            raise Return((True, None))

        project_id = self.project['_id']

        for category_name, channels in six.iteritems(unsubscribe_from):

            if category_name not in self.categories:
                # attempt to unsubscribe from not allowed category
                continue

            if not channels or not isinstance(channels, list):
                # attempt to unsubscribe from unknown channels
                continue

            category_id = self.categories[category_name]['_id']

            for channel in channels:

                allowed_channels = self.permissions[category_name] if self.permissions else []

                if allowed_channels and channel not in allowed_channels:
                    # attempt to unsubscribe from not allowed channel
                    continue

                channel_to_unsubscribe = rpc.create_channel_name(
                    project_id,
                    category_id,
                    channel
                )
                self.sub_stream.setsockopt_string(
                    zmq.UNSUBSCRIBE, six.u(channel_to_unsubscribe)
                )

                try:
                    del self.channels[category_name][channel_to_unsubscribe]
                except KeyError:
                    pass

        raise Return((True, None))

    @coroutine
    def handle_broadcast(self, params):

        category = params.get('category')
        channel = params.get('channel')

        if category not in self.categories:
            raise Return((None, 'category permission denied'))

        if category not in self.bidirectional_categories:
            raise Return((None, 'one-way category'))

        allowed_channels = self.permissions.get(category) if self.permissions else []

        if allowed_channels and channel not in allowed_channels:
            # attempt to broadcast into not allowed channel
            raise Return((None, 'channel permission denied'))

        result, error = yield rpc.process_broadcast(
            self.application,
            self.project,
            self.bidirectional_categories,
            params
        )

        raise Return((result, error))

    @coroutine
    def on_centrifuge_connection_message(self, message):
        """
        Called when message from client received.
        """
        try:
            data = json_decode(message)
        except ValueError:
            self.send_ack(error='malformed JSON data')
            raise Return(False)

        try:
            validate(data, req_schema)
        except ValidationError as e:
            self.send_ack(error=str(e))

        msg_id = data.get('id', None)
        method = data.get('method')
        params = data.get('params')

        if method != 'auth' and not self.is_authenticated:
            self.send_ack(error='unauthorized')
            raise Return(True)

        func = getattr(self, 'handle_%s' % method, None)

        if not func:
            self.send_ack(
                msg_id=msg_id,
                method=method,
                error="unknown method %s" % method
            )

        try:
            validate(params, client_params_schema[method])
        except ValidationError as e:
            self.send_ack(msg_id=msg_id, method=method, error=str(e))
            raise Return(True)

        result, error = yield func(params)

        self.send_ack(msg_id=msg_id, method=method, result=result, error=error)

        raise Return(True)

    def start_heartbeat(self):
        """
        In ideal case we work with websocket connections with heartbeat available
        by default. But there are lots of other transports whose heartbeat must be
        started manually. Do it here.
        """
        if isinstance(self, SockJSConnection):
            if self.session:
                if self.session.transport_name != 'websocket':
                    self.session.start_heartbeat()
            else:
                self.close_connection()

    def on_message_published(self, message):
        """
        Called when message received from one of channels client subscribed to.
        """
        actual_message = message[0]
        if six.PY3:
            actual_message = actual_message.decode()
        self.send_message(
            actual_message.split(rpc.CHANNEL_DATA_SEPARATOR, 1)[1]
        )

    def clean_up(self):
        """
        Unsubscribe connection from channels, clean up zmq sockets.
        """
        if hasattr(self, 'sub_stream') and not self.sub_stream.closed():
            self.sub_stream.on_recv(None)
            self.sub_stream.close()

        if not self.is_authenticated:
            return

        project_id = self.project['_id']

        connections = self.application.connections

        self.channels = None

        if not project_id in connections:
            return

        if not self.user in connections[project_id]:
            return

        try:
            del connections[project_id][self.user][self.uid]
        except KeyError:
            pass

        # clean connections
        if not connections[project_id][self.user]:
            try:
                del connections[project_id][self.user]
            except KeyError:
                pass
            if not connections[project_id]:
                try:
                    del connections[project_id]
                except KeyError:
                    pass

    def on_centrifuge_connection_open(self):
        logger.info('client connected')
        self.is_authenticated = False

    def on_centrifuge_connection_close(self):
        logger.info('client disconnected')
        self.clean_up()


class SockjsConnection(Connection, SockJSConnection):

    def on_message(self, message):
        self.on_centrifuge_connection_message(message)

    def on_open(self, info):
        self.on_centrifuge_connection_open()

    def on_close(self):
        self.on_centrifuge_connection_close()


class WebsocketConnection(Connection, WebSocketHandler):

    def open(self):
        self.on_centrifuge_connection_open()

    def on_close(self):
        self.on_centrifuge_connection_close()

    def on_message(self, message):
        self.on_centrifuge_connection_message(message)