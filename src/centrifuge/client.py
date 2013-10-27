# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import six
import uuid
import time
import random

try:
    from urllib import urlencode
except ImportError:
    # python 3
    # noinspection PyUnresolvedReferences
    from urllib.parse import urlencode

from tornado.ioloop import IOLoop, PeriodicCallback
from tornado.httpclient import AsyncHTTPClient, HTTPRequest
from tornado.escape import json_decode
from tornado.gen import coroutine, Return, Task

from jsonschema import validate, ValidationError

from centrifuge import auth
from centrifuge.response import Response
from centrifuge.log import logger
from centrifuge.schema import req_schema, client_api_schema


@coroutine
def sleep(seconds):
    """
    Non-blocking sleep.
    """
    awake_at = time.time() + seconds
    yield Task(IOLoop.instance().add_timeout, awake_at)
    raise Return((True, None))


class Client(object):
    """
    This class describes a single connection of client.
    """
    application = None

    def __init__(self, sock, info):
        self.sock = sock
        self.info = info
        self.uid = uuid.uuid4().hex
        self.is_authenticated = False
        self.user = ''
        self.channel_user_info = {}
        self.default_user_info = {}
        self.project_id = None
        self.channels = None
        self.presence_ping = None
        logger.debug("new client created (uid: {0}, ip: {1})".format(
            self.uid, getattr(self.info, 'ip', '-')
        ))

    @coroutine
    def close(self):
        yield self.clean()
        logger.debug('client destroyed (uid: %s)' % self.uid)
        raise Return((True, None))

    @coroutine
    def clean(self):
        """
        Must be called when client connection closes. Here we are
        making different clean ups.
        """
        if self.presence_ping:
            self.presence_ping.stop()

        project_id = self.project_id

        if not project_id:
            raise Return((True, None))

        if not self.is_authenticated:
            raise Return((True, None))

        self.application.remove_connection(
            project_id, self.user, self.uid
        )

        for namespace_name, channels in six.iteritems(self.channels):
            for channel, status in six.iteritems(channels):
                yield self.application.state.remove_presence(
                    project_id, namespace_name, channel, self.uid
                )

                self.application.pubsub.remove_subscription(
                    project_id, namespace_name, channel, self
                )

                project, error = yield self.get_project(self.project_id)
                if not error and project:
                    namespace, error = yield self.get_namespace(
                        project, {"namespace": namespace_name}
                    )
                    if namespace and namespace.get("join_leave", False):
                        self.send_leave_message(namespace_name, channel)

        self.channels = None
        self.channel_user_info = None
        self.default_user_info = None
        self.sock = None
        raise Return((True, None))

    def send(self, response):
        """
        Send message directly to client.
        """
        self.sock.send(response)

    @coroutine
    def message_received(self, message):
        """
        Called when message from client received.
        """
        response = Response()

        try:
            data = json_decode(message)
        except ValueError:
            response.error = 'malformed JSON data'
            self.send(response.as_message())
            yield self.sock.close()
            raise Return((True, None))

        try:
            validate(data, req_schema)
        except ValidationError as e:
            response.error = str(e)
            self.send(response.as_message())
            yield self.sock.close()
            raise Return((True, None))

        uid = data.get('uid', None)
        method = data.get('method')
        params = data.get('params')

        response.uid = uid
        response.method = method
        response.params = params

        if method != 'connect' and not self.is_authenticated:
            response.error = self.application.UNAUTHORIZED
            self.send(response.as_message())
            yield self.sock.close()
            raise Return((True, None))

        func = getattr(self, 'handle_%s' % method, None)

        if not func:
            response.error = "unknown method %s" % method
            self.send(response.as_message())
            yield self.sock.close()
            raise Return((True, None))

        if method not in client_api_schema:
            raise Return((None, 'unknown method %s' % method))

        try:
            validate(params, client_api_schema[method])
        except ValidationError as e:
            response = Response(uid=uid, method=method, error=str(e))
            self.send(response.as_message())
            yield self.sock.close()
            raise Return((True, None))

        response.body, response.error = yield func(params)
        self.send(response.as_message())
        raise Return((True, None))

    @coroutine
    def send_presence_ping(self):
        """
        Update presence information for all channels this client
        subscribed to.
        """
        for namespace, channels in six.iteritems(self.channels):
            for channel, status in six.iteritems(channels):
                user_info = self.get_user_info(namespace, channel)
                yield self.application.state.add_presence(
                    self.project_id, namespace, channel, self.uid, user_info
                )

    def get_user_info(self, namespace_name, channel):
        """
        Return channel specific user info.
        """
        try:
            channel_user_info = self.channel_user_info[namespace_name][channel]
        except KeyError:
            channel_user_info = None
        default_info = self.default_user_info.copy()
        default_info.update({
            'channel_info': channel_user_info
        })
        return default_info

    def update_channel_user_info(self, body, namespace_name, channel):
        """
        Try to extract channel specific user info from response body
        and keep it for channel.
        """
        try:
            info = json_decode(body)
        except Exception as e:
            logger.error(str(e))
            info = {}

        self.channel_user_info.setdefault(namespace_name, {})
        self.channel_user_info[namespace_name][channel] = info

    @coroutine
    def authorize(self, auth_address, project, namespace_name, channel):
        """
        Send POST request to web application to ask it if current client
        has a permission to subscribe on channel.
        """
        project_id = self.project_id

        http_client = AsyncHTTPClient()
        request = HTTPRequest(
            auth_address,
            method="POST",
            body=urlencode({
                'user': self.user,
                'namespace': namespace_name,
                'channel': channel
            }),
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
            except Exception as e:
                # let it fail and try again after some timeout
                # until we have auth attempts
                logger.debug(e)
            else:
                # reset back-off attempts
                self.application.back_off[project_id] = 0

                if response.code == 200:
                    # auth successful
                    self.update_channel_user_info(response.body, namespace_name, channel)
                    raise Return((True, None))

                elif response.code == 403:
                    # access denied for this client
                    raise Return((False, None))
            attempts += 1
            self.application.back_off[project_id] += 1

        raise Return((False, None))

    @coroutine
    def handle_connect(self, params):
        """
        Authenticate client's connection, initialize required
        variables in case of successful authentication.
        """
        if self.is_authenticated:
            raise Return((True, None))

        token = params["token"]
        user = params["user"]
        project_id = params["project"]
        user_info = params.get("info", None)

        project, error = yield self.get_project(project_id)
        if error:
            raise Return((None, error))

        secret_key = project['secret_key']

        if token != auth.get_client_token(secret_key, project_id, user, user_info=user_info):
            raise Return((None, "invalid token"))

        if user_info is not None:
            try:
                user_info = json_decode(user_info)
            except Exception as err:
                logger.debug("malformed JSON data in user_info")
                logger.debug(err)
                user_info = None

        self.is_authenticated = True
        self.project_id = project_id
        self.user = user
        self.default_user_info = {
            'user_id': self.user,
            'client_id': self.uid,
            'default_info': user_info,
            'channel_info': None
        }
        self.channels = {}

        if not self.application.state.fake:
            self.presence_ping = PeriodicCallback(
                self.send_presence_ping, self.application.state.presence_ping_interval
            )
            self.presence_ping.start()

        raise Return((self.uid, None))

    @coroutine
    def handle_subscribe(self, params):
        """
        Subscribe client on channel.
        """
        project, error = yield self.get_project(self.project_id)
        if error:
            raise Return((None, error))

        namespace, error = yield self.get_namespace(project, params)
        if error:
            raise Return((None, error))
        namespace_name = namespace['name']

        channel = params.get('channel')
        if not channel:
            raise Return((None, 'channel required'))

        project_id = self.project_id

        self.application.add_connection(project_id, self.user, self.uid, self)

        is_private = namespace.get('is_private', False)

        if is_private:
            auth_address = namespace.get('auth_address', None)
            if not auth_address:
                auth_address = project.get('auth_address', None)
            if not auth_address:
                raise Return((None, 'no auth address found'))
            is_authorized, error = yield self.authorize(
                auth_address, project, namespace_name, channel
            )
            if error:
                raise Return((None, self.application.INTERNAL_SERVER_ERROR))
            if not is_authorized:
                raise Return((None, self.application.PERMISSION_DENIED))

        self.application.pubsub.add_subscription(
            project_id, namespace_name, channel, self
        )

        if namespace_name not in self.channels:
            self.channels[namespace_name] = {}

        self.channels[namespace_name][channel] = True

        user_info = self.get_user_info(namespace_name, channel)

        yield self.application.state.add_presence(
            project_id, namespace_name, channel, self.uid, user_info
        )

        if namespace.get('join_leave', False):
            self.send_join_message(namespace_name, channel)

        raise Return((True, None))

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe client from channel.
        """
        project, error = yield self.get_project(self.project_id)
        if error:
            raise Return((None, error))

        namespace, error = yield self.get_namespace(project, params)
        if error:
            raise Return((None, error))
        namespace_name = namespace['name']

        channel = params.get('channel')

        if not channel:
            raise Return((True, None))

        project_id = self.project_id

        self.application.pubsub.remove_subscription(
            project_id, namespace_name, channel, self
        )

        try:
            del self.channels[namespace_name][channel]
        except KeyError:
            pass

        if namespace_name in self.channels and not self.channels[namespace_name]:
            try:
                del self.channels[namespace_name]
            except KeyError:
                pass

        yield self.application.state.remove_presence(
            project_id, namespace_name, channel, self.uid
        )

        if namespace.get('join_leave', False):
            self.send_leave_message(namespace_name, channel)

        raise Return((True, None))

    def check_channel_permission(self, namespace, channel):
        """
        Check that user subscribed on channel.
        """
        if namespace in self.channels and channel in self.channels[namespace]:
            return
        raise Return((None, self.application.PERMISSION_DENIED))

    @coroutine
    def handle_publish(self, params):
        """
        Publish message into channel.
        """
        project, error = yield self.get_project(self.project_id)
        if error:
            raise Return((None, error))

        namespace, error = yield self.get_namespace(project, params)
        if error:
            raise Return((None, error))
        namespace_name = namespace['name']

        channel = params.get('channel')

        self.check_channel_permission(namespace_name, channel)

        if not namespace['publish']:
            raise Return((None, 'publishing into this namespace not available'))

        user_info = self.get_user_info(namespace_name, channel)

        result, error = yield self.application.process_publish(
            project,
            params,
            client=user_info
        )
        raise Return((result, error))

    @coroutine
    def handle_presence(self, params):
        """
        Get presence information for channel.
        """
        project, error = yield self.get_project(self.project_id)
        if error:
            raise Return((None, error))

        namespace, error = yield self.get_namespace(project, params)
        if error:
            raise Return((None, error))
        namespace_name = namespace['name']

        channel = params.get('channel')

        self.check_channel_permission(namespace_name, channel)

        if not namespace['presence']:
            raise Return((None, 'presence for this namespace not available'))

        result, error = yield self.application.process_presence(
            project,
            params
        )
        raise Return((result, error))

    @coroutine
    def handle_history(self, params):
        """
        Get message history for channel.
        """
        project, error = yield self.get_project(self.project_id)
        if error:
            raise Return((None, error))

        namespace, error = yield self.get_namespace(project, params)
        if error:
            raise Return((None, error))
        namespace_name = namespace['name']

        channel = params.get('channel')

        self.check_channel_permission(namespace_name, channel)

        if not namespace['history']:
            raise Return((None, 'history for this namespace not available'))

        result, error = yield self.application.process_history(
            project,
            params
        )
        raise Return((result, error))

    @coroutine
    def get_project(self, project_id):
        """
        Project settings can change during client's connection.
        Every time we need project - we must extract actual
        project data from structure.
        """
        project, error = yield self.application.structure.get_project_by_id(project_id)
        if error:
            raise Return((None, self.application.INTERNAL_SERVER_ERROR))
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))
        raise Return((project, None))

    @coroutine
    def get_namespace(self, project, params):
        """
        Return actual namespace data for project.
        Note that namespace name can be None here - in this
        case we search for default project namespace and return
        it if exists.
        """
        namespace_name = params.get('namespace')
        namespace, error = yield self.application.structure.get_namespace_by_name(
            project, namespace_name
        )
        if error:
            raise Return((None, self.application.INTERNAL_SERVER_ERROR))
        if not namespace:
            raise Return((None, self.application.NAMESPACE_NOT_FOUND))
        raise Return((namespace, None))

    def send_join_message(self, namespace_name, channel):
        """
        Send join message to all channel subscribers when client
        subscribed on channel.
        """
        subscription_key = self.application.pubsub.get_subscription_key(
            self.project_id, namespace_name, channel
        )
        user_info = self.get_user_info(namespace_name, channel)
        message = {
            "namespace": namespace_name,
            "channel": channel,
            "data": user_info
        }
        self.application.pubsub.publish(
            subscription_key, message, method='join'
        )

    def send_leave_message(self, namespace_name, channel):
        """
        Send leave message to all channel subscribers when client
        unsubscribed from channel.
        """
        subscription_key = self.application.pubsub.get_subscription_key(
            self.project_id, namespace_name, channel
        )
        user_info = self.get_user_info(namespace_name, channel)
        message = {
            "namespace": namespace_name,
            "channel": channel,
            "data": user_info
        }
        self.application.pubsub.publish(
            subscription_key, message, method='leave'
        )
