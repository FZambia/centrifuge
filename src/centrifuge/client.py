# coding: utf-8
#
# Copyright (c) Alexandr Emelin. MIT license.
# All rights reserved.

import six
import hmac
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
from centrifuge.response import Response, MultiResponse
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
        self.token = None
        self.channel_user_info = {}
        self.default_user_info = {}
        self.project_id = None
        self.channels = None
        self.presence_ping = None
        self.extend = None
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

        if self.extend:
            self.extend.stop()

        project_id = self.project_id

        if project_id:

            self.application.remove_connection(
                project_id, self.user, self.uid
            )

            if self.channels is not None:

                channels = self.channels.copy()

                for namespace_name, channel_names in six.iteritems(channels):

                    if not channel_names:
                        continue

                    for channel_name, status in six.iteritems(channel_names):
                        if self.application.state:
                            yield self.application.state.remove_presence(
                                project_id, namespace_name, channel_name, self.uid
                            )

                        self.application.pubsub.remove_subscription(
                            project_id, namespace_name, channel_name, self
                        )

                        project, error = yield self.get_project(project_id)
                        if not error and project:
                            namespace, error = yield self.get_namespace(
                                project, {"namespace": namespace_name}
                            )
                            if namespace and namespace.get("join_leave", False):
                                self.send_leave_message(namespace_name, channel_name)

        self.channels = None
        self.channel_user_info = None
        self.default_user_info = None
        self.project_id = None
        self.is_authenticated = False
        self.sock = None
        self.token = None
        raise Return((True, None))

    @coroutine
    def close_sock(self, pause=True):
        """
        Force closing SockJS connection.
        """

        if pause:
            # sleep for a while before closing connection to prevent mass invalid reconnects
            yield sleep(1)

        try:
            if self.sock:
                self.sock.close()
            else:
                yield self.close()
        except Exception as err:
            logger.error(err)
        raise Return((True, None))

    @coroutine
    def send(self, response):
        """
        Send message directly to client.
        """
        if not self.sock:
            raise Return((False, None))

        try:
            self.sock.send(response)
        except Exception as err:
            logger.exception(err)
            yield self.close_sock(pause=False)
            raise Return((False, None))

        raise Return((True, None))

    @coroutine
    def process_obj(self, obj):

        response = Response()

        try:
            validate(obj, req_schema)
        except ValidationError as e:
            response.error = str(e)
            raise Return((response, response.error))

        uid = obj.get('uid', None)
        method = obj.get('method')
        params = obj.get('params')

        response.uid = uid
        response.method = method
        response.params = params

        if method != 'connect' and not self.is_authenticated:
            response.error = self.application.UNAUTHORIZED
            raise Return((response, response.error))

        func = getattr(self, 'handle_%s' % method, None)

        if not func or not method in client_api_schema:
            response.error = "unknown method %s" % method
            raise Return((response, response.error))

        try:
            validate(params, client_api_schema[method])
        except ValidationError as e:
            response.error = str(e)
            raise Return((response, response.error))

        response.body, response.error = yield func(params)

        raise Return((response, None))

    @coroutine
    def message_received(self, message):
        """
        Called when message from client received.
        """
        multi_response = MultiResponse()

        try:
            data = json_decode(message)
        except ValueError:
            logger.error('malformed JSON data')
            yield self.close_sock()
            raise Return((True, None))

        if isinstance(data, dict):
            # single object request
            response, err = yield self.process_obj(data)
            multi_response.add(response)
            if err:
                # error occurred, connection must be closed
                logger.error(err)
                yield self.sock.send(multi_response.as_message())
                yield self.close_sock()
                raise Return((True, None))

        elif isinstance(data, list):
            # multiple object request
            if len(data) > self.application.CLIENT_API_MESSAGE_LIMIT:
                logger.debug("client API message limit exceeded")
                yield self.close_sock()
                raise Return((True, None))

            for obj in data:
                response, err = yield self.process_obj(obj)
                multi_response.add(response)
                if err:
                    # close connection in case of any error
                    logger.error(err)
                    yield self.sock.send(multi_response.as_message())
                    yield self.close_sock()
                    raise Return((True, None))

        else:
            logger.error('data not list and not dictionary')
            yield self.close_sock()
            raise Return((True, None))

        yield self.send(multi_response.as_message())

        raise Return((True, None))

    @coroutine
    def send_presence_ping(self):
        """
        Update presence information for all channels this client
        subscribed to.
        """
        if not self.application.state:
            raise Return((True, None))
        for namespace, channels in six.iteritems(self.channels):
            for channel, status in six.iteritems(channels):
                user_info = self.get_user_info(namespace, channel)
                yield self.application.state.add_presence(
                    self.project_id, namespace, channel, self.uid, user_info
                )
        raise Return((True, None))

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
            except Exception as err:
                # let it fail and try again after some timeout
                # until we have auth attempts
                logger.debug(err)
            else:
                # reset back-off attempts
                self.application.back_off[project_id] = 0

                if response.code == 200:
                    # auth successful
                    self.update_channel_user_info(response.body, namespace_name, channel)
                    raise Return((True, None))

                else:
                    # access denied for this client
                    raise Return((False, None))
            attempts += 1
            self.application.back_off[project_id] += 1

        raise Return((False, None))

    @coroutine
    def handle_ping(self, params):
        """
        Some hosting platforms (for example Heroku) disconnect websocket
        connection after a while if no payload transfer over network. To
        prevent such disconnects clients can periodically send ping messages
        to Centrifuge.
        """
        raise Return(('pong', None))

    @coroutine
    def handle_connect(self, params):
        """
        Authenticate client's connection, initialize required
        variables in case of successful authentication.
        """
        if self.is_authenticated:
            raise Return((self.uid, None))

        token = params["token"]
        user = params["user"]
        project_id = params["project"]
        timestamp = params["timestamp"]
        user_info = params.get("info", None)
        extended_token = params.get("extended_token")
        extended_timestamp = params.get("extended_timestamp")

        project, error = yield self.get_project(project_id)
        if error:
            raise Return((None, error))

        secret_key = project['secret_key']

        if token != auth.get_client_token(secret_key, project_id, user, timestamp, user_info=user_info):
            raise Return((None, "invalid token"))

        self.check_token_expire(project, token, timestamp, extended_token, extended_timestamp)

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
        self.token = token
        self.default_user_info = {
            'user_id': self.user,
            'client_id': self.uid,
            'default_info': user_info,
            'channel_info': None
        }
        self.channels = {}

        if self.application.state:
            self.presence_ping = PeriodicCallback(
                self.send_presence_ping, self.application.state.presence_ping_interval
            )
            self.presence_ping.start()

        raise Return((self.uid, None))

    def check_token_expire(self, project, token, timestamp, extended_token, extended_timestamp):
        """
        Check that timestamp is valid and is not too old.
        If timestamp is expired then check extended credentials if present.
        """
        if not self.application.TOKEN_EXPIRE:
            return

        try:
            timestamp = int(timestamp)
        except ValueError:
            raise Return((None, "invalid timestamp"))

        now = time.time()
        if timestamp + self.application.TOKEN_EXPIRE_INTERVAL < now:
            # it seems that token expired, the only chance for client is to have
            # actual extended credentials in this request
            if extended_token and extended_timestamp:
                expected_token = self.get_extend_token(project, token, extended_timestamp)
                if expected_token != extended_token:
                    raise Return((None, "invalid extend token"))
                try:
                    extended_timestamp = int(extended_timestamp)
                except ValueError:
                    raise Return((None, "invalid extended timestamp"))
                if extended_timestamp + self.application.TOKEN_EXPIRE_INTERVAL < now:
                    raise Return((None, "connection expired"))
            else:
                raise Return((None, "connection expired"))

        last_timestamp = max(timestamp, extended_timestamp) if extended_timestamp else timestamp
        time_to_extend = self.application.TOKEN_EXTEND_INTERVAL - (now - last_timestamp)
        IOLoop.instance().add_timeout(time.time() + time_to_extend, self.send_extend_message)

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

        if self.application.state:
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

        if self.application.state:
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

        if not namespace.get('publish', False):
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

        if not namespace.get('presence', False):
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

        if not namespace.get('history', False):
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

    def send_join_leave_message(self, namespace_name, channel, message_method):
        """
        Generate and send message about join or leave event.
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
            subscription_key, message, method=message_method
        )

    def send_join_message(self, namespace_name, channel):
        """
        Send join message to all channel subscribers when client
        subscribed on channel.
        """
        self.send_join_leave_message(namespace_name, channel, 'join')

    def send_leave_message(self, namespace_name, channel):
        """
        Send leave message to all channel subscribers when client
        unsubscribed from channel.
        """
        self.send_join_leave_message(namespace_name, channel, 'leave')

    @staticmethod
    def get_extend_token(project, original_token, timestamp):
        """
        Create and return extend token based on project secret key, original
        token received on first connect and timestamp.
        """
        token = hmac.new(six.b(str(project['secret_key'])))
        token.update(six.b(original_token))
        token.update(six.b(timestamp))
        return token.hexdigest()

    @coroutine
    def generate_extend_credentials(self):
        """
        Generate extend token and timestamp.
        """
        project, error = yield self.get_project(self.project_id)
        if error:
            raise Return((None, error))

        now = str(int(time.time()))
        token = self.get_extend_token(project, self.token, now)
        raise Return(((token, now), None))

    @coroutine
    def send_extend_message(self):
        """
        Send message to current client with extend credentials:
        current timestamp and prolonged token based on project secret key,
        initial connect token and current timestamp. After receiving this
        message client must connect to Centrifuge with these credentials in
        addition to first connect parameters.
        """
        if not self.is_authenticated:
            raise Return(False)

        credentials, error = yield self.generate_extend_credentials()
        if error:
            raise Return(False)
        message_body = {
            "extended_token": credentials[0],
            "extended_timestamp": credentials[1]
        }
        response = Response(method="extend", body=message_body)
        yield self.send(response.as_message())

        if not self.extend:
            self.extend = PeriodicCallback(
                self.send_extend_message, self.application.TOKEN_EXTEND_INTERVAL*1000
            )
            self.extend.start()

        raise Return(True)
