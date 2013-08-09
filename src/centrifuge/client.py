# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import uuid
import six
import time
import random
from tornado.ioloop import IOLoop
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.escape import json_encode, json_decode
from tornado.gen import coroutine, Return, Task

from jsonschema import validate, ValidationError

import zmq
from zmq.eventloop.zmqstream import ZMQStream

from . import auth
from .core import Response, create_subscription_name
from .log import logger
from .schema import req_schema, client_params_schema


@coroutine
def sleep(seconds):
    """
    Non-blocking sleep.
    """
    yield Task(IOLoop.instance().add_timeout, time.time()+seconds)
    raise Return((True, None))


class Client(object):
    """
    This class describes a single connection of client from
    web browser.
    """
    application = None

    INTERNAL_SERVER_ERROR = 'internal server error'

    def __init__(self, sock, info):
        self.sock = sock
        self.info = info
        self.uid = uuid.uuid4().hex
        self.is_authenticated = False
        self.sub_stream = None
        logger.debug("new client created (uid: %s)" % self.uid)

    def close(self):
        self.clean()
        logger.info('client destroyed (uid: %s)' % self.uid)

    @coroutine
    def clean(self):
        if self.sub_stream and not self.sub_stream.closed():
            self.sub_stream.stop_on_recv()
            self.sub_stream.close()

        if not self.is_authenticated:
            return

        project_id = self.project['_id']

        connections = self.application.connections

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

        for category, channels in six.iteritems(self.channels):
            for channel, status in six.iteritems(channels):
                yield self.application.state.remove_presence(
                    project_id, category, channel, self.uid
                )

        self.channels = None

        self.sock.close()
        self.sock = None

    def send(self, response):
        self.sock.send(response.as_message())

    def message_published(self, message):
        """
        Called when message received from one of channels client subscribed to.
        """
        actual_message = message[1]
        if six.PY3:
            actual_message = actual_message.decode()
        response = Response(method="message", body=actual_message)
        self.send(response)

    @coroutine
    def message_received(self, message):

        response = Response()

        print message

        try:
            data = json_decode(message)
        except ValueError:
            response.error = 'malformed JSON data'
            self.send(response)
            raise Return(True)

        try:
            validate(data, req_schema)
        except ValidationError as e:
            response.error = str(e)
            self.send(response)
            raise Return(True)

        uid = data.get('uid', None)
        method = data.get('method')
        params = data.get('params')

        response.uid = uid
        response.method = method

        if method != 'auth' and not self.is_authenticated:
            response.error = 'unauthorized'
            self.send(response)
            raise Return(True)

        func = getattr(self, 'handle_%s' % method, None)

        if not func:
            response.error = "unknown method %s" % method
            self.send(response)
            raise Return(True)

        try:
            validate(params, client_params_schema[method])
        except ValidationError as e:
            response = Response(uid=uid, method=method, error=str(e))
            self.send(response)
            raise Return(True)

        response.body, response.error = yield func(params)
        self.send(response)
        raise Return(True)

    @coroutine
    def authorize(self, project, user, permissions):

        if not user or not project.get('validate_url', None):
            raise Return((True, None))

        project_id = project['_id']

        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            project['validate_url'],
            method="POST",
            body=json_encode({'user': user, 'permissions': permissions}),
            request_timeout=1
        )

        max_auth_attempts = project.get('max_auth_attempts')
        back_off_interval = project.get('back_off_interval')
        back_off_max_timeout = project.get('back_off_max_timeout')

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
            except:
                # let it fail and try again after some timeout
                # until we have auth attempts
                pass
            else:
                # reset back-off attempts
                self.application.back_off[project_id] = 0

                if response.code == 200:
                    raise Return((True, None))
                elif response.code == 403:
                    raise Return((False, None))
            attempts += 1
            self.application.back_off[project_id] += 1

        raise Return((False, None))

    @coroutine
    def handle_auth(self, params):

        if self.is_authenticated:
            raise Return((True, None))

        token = params["token"]
        user = params["user"]
        project_id = params["project_id"]
        permissions = params["permissions"]

        project, error = yield self.application.structure.get_project_by_id(project_id)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not project:
            raise Return((None, "project not found"))

        secret_key = project['secret_key']

        if token != auth.get_client_token(secret_key, project_id, user):
            raise Return((None, "invalid token"))

        self.is_authenticated, error = yield self.authorize(
            project, user, permissions
        )
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not self.is_authenticated:
            raise Return((None, 'unauthorized'))

        project_categories, error = yield self.application.structure.get_project_categories(
            project
        )
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))

        self.categories = {}
        for category in project_categories:
            if not permissions or (permissions and category['name'] in permissions):
                self.categories[category['name']] = category

        self.project = project
        self.permissions = permissions
        self.user = user
        self.user_info = json_encode({'user_id': self.user})
        self.channels = {}

        # allow publish from client only into bidirectional categories
        self.bidirectional_categories = {}
        for category_name, category in six.iteritems(self.categories):
            if category.get('is_bidirectional', False):
                self.bidirectional_categories[category_name] = category

        context = self.application.zmq_context
        subscribe_socket = context.socket(zmq.SUB)

        if self.application.zmq_pub_sub_proxy:
            subscribe_socket.connect(self.application.zmq_xpub)
        else:
            for address in self.application.zmq_sub_address:
                subscribe_socket.connect(address)

        self.sub_stream = ZMQStream(subscribe_socket)
        self.sub_stream.on_recv(self.message_published)

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

            allowed_channels = self.permissions.get(category_name) if self.permissions else []

            for channel in channels:

                if not isinstance(allowed_channels, list):
                    continue

                if allowed_channels and channel not in allowed_channels:
                    # attempt to subscribe on not allowed channel
                    continue

                channel_to_subscribe = create_subscription_name(
                    project_id,
                    category_name,
                    channel
                )

                self.sub_stream.setsockopt_string(
                    zmq.SUBSCRIBE, six.u(channel_to_subscribe)
                )

                if category_name not in self.channels:
                    self.channels[category_name] = {}

                self.channels[category_name][channel] = True

                self.application.state.add_presence(
                    project_id, category_name, channel, self.uid, self.user_info
                )

        raise Return((True, None))

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe authenticated connection from channels.
        """
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

            for channel in channels:

                allowed_channels = self.permissions[category_name] if self.permissions else []

                if allowed_channels and channel not in allowed_channels:
                    # attempt to unsubscribe from not allowed channel
                    continue

                channel_to_unsubscribe = self.application.create_subscription_name(
                    project_id,
                    category_name,
                    channel
                )
                self.sub_stream.setsockopt_string(
                    zmq.UNSUBSCRIBE, six.u(channel_to_unsubscribe)
                )

                try:
                    del self.channels[category_name][channel]
                except KeyError:
                    pass

                yield self.application.state.remove_presence(
                    project_id, category_name, channel, self.uid
                )

        raise Return((True, None))

    @coroutine
    def handle_publish(self, params):

        category = params.get('category')

        channel = params.get('channel')

        if category not in self.categories:
            raise Return((None, 'category does not exist or permission denied'))

        if category not in self.bidirectional_categories:
            raise Return((None, 'one-way category'))

        allowed_channels = self.permissions.get(category) if self.permissions else []

        if allowed_channels and channel not in allowed_channels:
            # attempt to publish into not allowed channel
            raise Return((None, 'channel permission denied'))

        result, error = yield self.application.process_publish(
            self.project,
            params,
            allowed_categories=self.bidirectional_categories
        )

        raise Return((result, error))
