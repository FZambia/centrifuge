# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import uuid
import six
import time
import random
try:
    from urllib import urlencode
except ImportError:
    from urllib.parse import urlencode
from tornado.ioloop import IOLoop, PeriodicCallback
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
        self.user_details = {}
        logger.debug("new client created (uid: %s)" % self.uid)

    @coroutine
    def close(self):
        yield self.clean()
        logger.info('client destroyed (uid: %s)' % self.uid)
        raise Return((True, None))

    @coroutine
    def clean(self):
        if self.sub_stream and not self.sub_stream.closed():
            self.sub_stream.stop_on_recv()
            self.sub_stream.close()

        if not self.is_authenticated:
            raise Return((True, None))

        project_id = self.project['_id']

        connections = self.application.connections

        if not project_id in connections:
            raise Return((True, None))

        if not self.user in connections[project_id]:
            raise Return((True, None))

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

        self.presence_ping.stop()

        for category, channels in six.iteritems(self.channels):
            for channel, status in six.iteritems(channels):
                yield self.application.state.remove_presence(
                    project_id, category, channel, self.uid
                )

        self.channels = None
        self.sock = None
        raise Return((True, None))

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

        try:
            data = json_decode(message)
        except ValueError:
            response.error = 'malformed JSON data'
            self.send(response)
            yield self.sock.close()
            raise Return((True, None))

        try:
            validate(data, req_schema)
        except ValidationError as e:
            response.error = str(e)
            self.send(response)
            yield self.sock.close()
            raise Return((True, None))

        uid = data.get('uid', None)
        method = data.get('method')
        params = data.get('params')

        response.uid = uid
        response.method = method
        response.params = params

        if method != 'connect' and not self.is_authenticated:
            response.error = 'unauthorized'
            self.send(response)
            yield self.sock.close()
            raise Return((True, None))

        func = getattr(self, 'handle_%s' % method, None)

        if not func:
            response.error = "unknown method %s" % method
            self.send(response)
            yield self.sock.close()
            raise Return((True, None))

        try:
            validate(params, client_params_schema[method])
        except ValidationError as e:
            response = Response(uid=uid, method=method, error=str(e))
            self.send(response)
            yield self.sock.close()
            raise Return((True, None))

        response.body, response.error = yield func(params)
        self.send(response)
        raise Return((True, None))

    @coroutine
    def authorize(self, auth_address, category_name, channel):

        project_id = self.project['_id']
        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            auth_address,
            method="POST",
            body=urlencode({
                'user': self.user,
                'category': category_name,
                'channel': channel
            }),
            request_timeout=1
        )

        max_auth_attempts = self.project.get('max_auth_attempts')
        back_off_interval = self.project.get('back_off_interval')
        back_off_max_timeout = self.project.get('back_off_max_timeout')

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
                    # auth successful
                    raise Return((True, None))

                elif response.code == 403:
                    # access denied for this client
                    raise Return((False, None))
            attempts += 1
            self.application.back_off[project_id] += 1

        raise Return((False, None))

    @coroutine
    def send_presence_ping(self):
        for category, channels in six.iteritems(self.channels):
            for channel, status in six.iteritems(channels):
                yield self.application.state.add_presence(
                    self.project['_id'], category, channel, self.uid, self.user_info
                )

    @coroutine
    def handle_connect(self, params):

        if self.is_authenticated:
            raise Return((True, None))

        token = params["token"]
        user = params["user"]
        project_id = params["project"]

        project, error = yield self.application.structure.get_project_by_id(project_id)
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))
        if not project:
            raise Return((None, "project not found"))

        secret_key = project['secret_key']

        if token != auth.get_client_token(secret_key, project_id, user):
            raise Return((None, "invalid token"))

        self.is_authenticated = True
        self.project = project
        self.user = user
        self.user_details.update({'user_id': self.user})
        self.user_info = json_encode(self.user_details)
        self.channels = {}
        self.presence_ping = PeriodicCallback(
            self.send_presence_ping, self.application.presence_ping_interval
        )
        self.presence_ping.start()

        context = self.application.zmq_context
        subscribe_socket = context.socket(zmq.SUB)

        if self.application.zmq_pub_sub_proxy:
            subscribe_socket.connect(self.application.zmq_xpub)
        else:
            for address in self.application.zmq_sub_address:
                subscribe_socket.connect(address)

        self.sub_stream = ZMQStream(subscribe_socket)
        self.sub_stream.on_recv(self.message_published)

        raise Return((self.uid, None))

    @coroutine
    def handle_subscribe(self, params):
        """
        Subscribe authenticated connection on channels.
        """
        category_name = params.get('category')
        channel = params.get('channel')

        if not category_name or not channel:
            raise Return((None, 'no category or channel provided'))

        project_id = self.project['_id']

        connections = self.application.connections

        if project_id not in connections:
            connections[project_id] = {}

        if self.user and self.user not in connections:
            connections[project_id][self.user] = {}

        if self.user:
            connections[project_id][self.user][self.uid] = self

        category, error = yield self.get_category(category_name)
        if error:
            raise Return((None, error))

        is_protected = category.get('is_protected', False)

        if is_protected:
            auth_address = category.get('auth_address', None)
            if not auth_address:
                auth_address = self.project.get('auth_address', None)
            if not auth_address:
                raise Return((None, 'no auth address found'))
            is_authorized, error = yield self.authorize(auth_address, category_name, channel)
            if error:
                raise Return((None, self.INTERNAL_SERVER_ERROR))
            if not is_authorized:
                raise Return((None, 'permission denied'))

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

        yield self.application.state.add_presence(
            project_id, category_name, channel, self.uid, self.user_info
        )

        raise Return((True, None))

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe authenticated connection from channels.
        """
        category_name = params.get('category')
        channel = params.get('channel')

        if not category_name or not channel:
            raise Return((True, None))

        project_id = self.project['_id']

        categories, error = yield self.application.structure.categories_by_name().get(
            project_id, {}
        )
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))

        if category_name not in categories:
            # attempt to unsubscribe from not allowed category
            raise Return((True, None))

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
    def get_category(self, category_name):
        categories, error = yield self.application.structure.get_categories_by_name()
        if error:
            raise Return((None, self.INTERNAL_SERVER_ERROR))

        project_categories = categories.get(
            self.project['_id'], {}
        )
        if category_name not in project_categories:
            raise Return((None, 'category does not exist'))

        raise Return((project_categories[category_name], None))

    def check_channel_permission(self, category, channel):
        if category in self.channels and channel in self.channels[category]:
            return
        raise Return((None, 'channel permission denied'))

    @coroutine
    def handle_publish(self, params):

        category_name = params.get('category')
        channel = params.get('channel')

        category, error = yield self.get_category(category_name)
        if error:
            raise Return((None, error))

        self.check_channel_permission(category_name, channel)

        if not category['publish']:
            raise Return((None, 'publishing into this category not available'))

        result, error = yield self.application.process_publish(
            self.project,
            params
        )
        raise Return((result, error))

    @coroutine
    def handle_presence(self, params):
        category_name = params.get('category')
        channel = params.get('channel')

        category, error = yield self.get_category(category_name)
        if error:
            raise Return((None, error))
        self.check_channel_permission(category_name, channel)

        if not category['presence']:
            raise Return((None, 'presence for this category not available'))

        result, error = yield self.application.process_presence(
            self.project,
            params
        )
        raise Return((result, error))

    @coroutine
    def handle_history(self, params):
        category_name = params.get('category')
        channel = params.get('channel')

        category, error = yield self.get_category(category_name)
        if error:
            raise Return((None, error))
        self.check_channel_permission(category_name, channel)

        if not category['history']:
            raise Return((None, 'history for this category not available'))

        result, error = yield self.application.process_history(
            self.project,
            params
        )
        raise Return((result, error))