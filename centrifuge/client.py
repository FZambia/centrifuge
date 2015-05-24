# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import six
import uuid
import time

try:
    from urllib import urlencode
except ImportError:
    # python 3
    # noinspection PyUnresolvedReferences
    from urllib.parse import urlencode

from tornado.ioloop import PeriodicCallback, IOLoop
from tornado.gen import coroutine, Return, sleep

from jsonschema import validate, ValidationError

from centrifuge import auth
from centrifuge.utils import json_decode
from centrifuge.response import Response, MultiResponse
from centrifuge.log import logger
from centrifuge.schema import req_schema, client_api_schema


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
        self.user = None
        self.timestamp = None
        self.channel_info = {}
        self.default_info = {}
        self.project_name = None
        self.channels = None
        self.presence_ping_task = None
        self.expire_timeout = None
        logger.info("client created via {0} (uid: {1}, ip: {2})".format(
            self.sock.session.transport_name, self.uid, getattr(self.info, 'ip', '-')
        ))

    @coroutine
    def close(self):
        logger.info('client destroyed (uid: %s)' % self.uid)
        yield self.clean()
        raise Return((True, None))

    @coroutine
    def clean(self):
        """
        Must be called when client connection closes. Here we are
        making different clean ups.
        """
        if self.presence_ping_task:
            self.presence_ping_task.stop()

        project_name = self.project_name

        if project_name:
            self.application.remove_connection(
                project_name, self.user, self.uid
            )

        if project_name and self.channels is not None:
            channels = self.channels.copy()
            for channel_name, channel_info in six.iteritems(channels):
                yield self.application.engine.remove_presence(
                    project_name, channel_name, self.uid
                )
                self.application.engine.remove_subscription(
                    project_name, channel_name, self
                )
                project = self.application.get_project(project_name)
                if project:
                    namespace = self.application.get_namespace(
                        project, channel_name
                    )
                    if namespace and namespace["join_leave"]:
                        self.send_leave_message(channel_name)

        self.channels = None
        self.channel_info = None
        self.default_info = None
        self.project_name = None
        self.is_authenticated = False
        self.sock = None
        self.user = None
        self.timestamp = None
        self.expire_timeout = None
        self.uid = None
        raise Return((True, None))

    @coroutine
    def close_sock(self, pause=True, pause_value=1):
        """
        Force closing connection.
        """
        if pause:
            # sleep for a while before closing connection to prevent mass invalid reconnects
            yield sleep(pause_value)

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

        if method not in ['connect'] and not self.is_authenticated:
            response.error = self.application.UNAUTHORIZED
            raise Return((response, response.error))

        func = getattr(self, 'handle_%s' % method, None)

        if not func or method not in client_api_schema:
            response.error = "unknown method %s" % method
            raise Return((response, response.error))

        try:
            schema_name = method
            if self.application.INSECURE and schema_name == 'connect':
                # if Centrifuge run in insecure mode we use simplified connection
                # schema to allow clients connect without timestamp and token
                schema_name = "connect_insecure"
            validate(params, client_api_schema[schema_name])
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
                logger.info("client API message limit exceeded")
                yield self.close_sock()
                raise Return((True, None))

            for obj in data:
                response, err = yield self.process_obj(obj)
                multi_response.add(response)
                if err:
                    # close connection in case of any error
                    logger.error(err)
                    yield self.sock.send(multi_response.as_message())
                    yield self.send_disconnect_message()
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
        for channel, channel_info in six.iteritems(self.channels):
            info = self.get_info(channel)
            if channel not in self.channels:
                continue
            yield self.application.engine.add_presence(
                self.project_name, channel, self.uid, info
            )
        raise Return((True, None))

    def get_info(self, channel):
        """
        Return channel specific user info.
        """
        try:
            channel_info = self.channel_info[channel]
        except KeyError:
            channel_info = None
        default_info = self.default_info.copy()
        default_info.update({
            'channel_info': channel_info
        })
        return default_info

    def update_channel_info(self, body, channel):
        """
        Try to extract channel specific user info from response body
        and keep it for channel.
        """
        try:
            info = json_decode(body)
        except Exception as e:
            logger.error(str(e))
            info = {}

        self.channel_info[channel] = info

    @coroutine
    def handle_ping(self, params):
        """
        Some hosting platforms (for example Heroku) disconnect websocket
        connection after a while if no payload transfer over network. To
        prevent such disconnects clients can periodically send ping messages
        to Centrifuge.
        """
        raise Return(('pong', None))

    @staticmethod
    def validate_token(token, secret, project_name, user, timestamp, user_info):
        try:
            is_valid_token = auth.check_client_token(
                token, secret, project_name, user, timestamp, user_info=user_info
            )
        except Exception as err:
            logger.error(err)
            return "invalid connection parameters"

        if not is_valid_token:
            return "invalid token"

        return None

    @coroutine
    def handle_connect(self, params):
        """
        Authenticate client's connection, initialize required
        variables in case of successful authentication.
        """
        if self.application.collector:
            self.application.collector.incr('connect')
            self.application.collector.incr(self.sock.session.transport_name)

        if self.is_authenticated:
            raise Return((self.uid, None))

        project_name = params["project"]
        user = params["user"]
        info = params.get("info", "")

        if not self.application.INSECURE:
            token = params["token"]
            timestamp = params["timestamp"]
        else:
            token = timestamp = None

        project = self.application.get_project(project_name)
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))

        secret = project['secret']

        if not self.application.INSECURE:
            error_msg = self.validate_token(
                token, secret, project_name, user, timestamp, info
            )
            if error_msg:
                raise Return((None, error_msg))

        if info:
            try:
                info = json_decode(info)
            except Exception as err:
                logger.error("malformed JSON data in user_info")
                logger.error(err)
                info = {}
        else:
            info = {}

        if not self.application.INSECURE:
            try:
                timestamp = int(timestamp)
            except ValueError:
                raise Return((None, "invalid timestamp"))
        else:
            # we are not interested in timestamp in case of insecure mode so just
            # set it to current timestamp
            timestamp = int(time.time())

        self.user = user
        self.project_name = project_name
        self.timestamp = timestamp

        time_to_expire = None
        if not self.application.INSECURE and project['connection_lifetime'] > 0:
            now = time.time()
            conn_lifetime = project["connection_lifetime"]
            time_to_expire = self.timestamp + conn_lifetime - now
            if time_to_expire <= 0:
                raise Return(({"client": None, "expired": True, "ttl": conn_lifetime}, None))

        # Welcome to Centrifuge dear Connection!
        self.is_authenticated = True
        self.default_info = {
            'user': self.user,
            'client': self.uid,
            'default_info': info,
            'channel_info': None
        }

        self.channels = {}
        self.presence_ping_task = PeriodicCallback(
            self.send_presence_ping, self.application.engine.presence_ping_interval
        )
        self.presence_ping_task.start()
        self.application.add_connection(project_name, self.user, self.uid, self)

        conn_lifetime = project["connection_lifetime"]

        if time_to_expire:
            self.expire_timeout = IOLoop.current().add_timeout(
                time.time() + conn_lifetime, self.expire
            )

        body = {
            "client": self.uid,
            "expired": False,
            "ttl": conn_lifetime if project["connection_lifetime"] > 0 else None
        }
        raise Return((body, None))

    @coroutine
    def expire(self):

        # give client a chance to save its connection
        yield sleep(self.application.EXPIRED_CONNECTION_CLOSE_DELAY)

        project = self.application.get_project(self.project_name)
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))

        if not project["connection_lifetime"] > 0:
            raise Return((True, None))

        conn_lifetime = project["connection_lifetime"]
        time_to_expire = self.timestamp + conn_lifetime - time.time()
        if time_to_expire > 0:
            # connection saved
            raise Return((True, None))

        # close connection immediately
        yield self.close_sock(pause=False)

        raise Return((True, None))

    @coroutine
    def handle_refresh(self, params):
        """
        Handle request with refreshed connection timestamp
        """
        project_name = params["project"]
        user = params["user"]
        timestamp = params["timestamp"]
        info = params.get("info", "")
        token = params["token"]

        project = self.application.get_project(project_name)
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))

        secret = project['secret']

        error_msg = self.validate_token(
            token, secret, project_name, user, timestamp, info
        )
        if error_msg:
            raise Return((None, error_msg))

        try:
            timestamp = int(timestamp)
        except ValueError:
            raise Return((None, "invalid timestamp"))

        conn_lifetime = project["connection_lifetime"]
        time_to_expire = timestamp + conn_lifetime - time.time()
        if time_to_expire > 0:
            self.timestamp = timestamp
            if self.expire_timeout:
                IOLoop.current().remove_timeout(self.expire_timeout)
            self.expire_timeout = IOLoop.current().add_timeout(
                time.time() + time_to_expire, self.expire
            )
        else:
            raise Return((None, "connection expired"))

        body = {
            "ttl": conn_lifetime if project["connection_lifetime"] > 0 else None
        }

        raise Return((body, None))

    @coroutine
    def handle_subscribe(self, params):
        """
        Subscribe client on channel.
        """
        project = self.application.get_project(self.project_name)
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))

        channel = params.get('channel')
        if not channel:
            raise Return((None, 'channel required'))

        if len(channel) > self.application.MAX_CHANNEL_LENGTH:
            raise Return((None, 'maximum channel length exceeded'))

        body = {
            "channel": channel,
        }

        if self.application.USER_CHANNEL_BOUNDARY in channel:
            users_allowed = self.application.get_allowed_users(channel)
            if self.user not in users_allowed:
                raise Return((body, self.application.PERMISSION_DENIED))

        namespace = self.application.get_namespace(project, channel)
        if not namespace:
            raise Return((body, self.application.NAMESPACE_NOT_FOUND))

        project_name = self.project_name

        anonymous = namespace['anonymous']
        if not anonymous and not self.user and not self.application.INSECURE:
            raise Return((body, self.application.PERMISSION_DENIED))

        is_private = self.application.is_channel_private(channel)

        if is_private:
            client = params.get("client", "")
            if client != self.uid:
                raise Return((body, self.application.UNAUTHORIZED))
            sign = params.get("sign", "")
            info = params.get("info", "")
            is_authorized = auth.check_channel_sign(
                sign, project["secret"], client, channel, info
            )
            if not is_authorized:
                raise Return((body, self.application.UNAUTHORIZED))

            self.update_channel_info(info, channel)

        yield self.application.engine.add_subscription(
            project_name, channel, self
        )

        self.channels[channel] = True

        info = self.get_info(channel)

        yield self.application.engine.add_presence(
            project_name, channel, self.uid, info
        )

        if namespace['join_leave']:
            self.send_join_message(channel)

        raise Return((body, None))

    @coroutine
    def handle_unsubscribe(self, params):
        """
        Unsubscribe client from channel.
        """
        project = self.application.get_project(self.project_name)
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))

        channel = params.get('channel')

        if not channel:
            raise Return((None, "channel required"))

        body = {
            "channel": channel,
        }

        namespace = self.application.get_namespace(project, channel)
        if not namespace:
            raise Return((body, self.application.NAMESPACE_NOT_FOUND))

        project_name = self.project_name

        yield self.application.engine.remove_subscription(
            project_name, channel, self
        )

        try:
            del self.channels[channel]
        except KeyError:
            pass

        yield self.application.engine.remove_presence(
            project_name, channel, self.uid
        )

        if namespace['join_leave']:
            self.send_leave_message(channel)

        raise Return((body, None))

    def check_channel_permission(self, channel):
        """
        Check that user subscribed on channel.
        """
        if channel in self.channels:
            return

        raise Return((None, self.application.PERMISSION_DENIED))

    @coroutine
    def handle_publish(self, params):
        """
        Publish message into channel.
        """
        project = self.application.get_project(self.project_name)
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))

        channel = params.get('channel')

        body = {
            "channel": channel,
            "status": False
        }

        self.check_channel_permission(channel)

        namespace = self.application.get_namespace(project, channel)
        if not namespace:
            raise Return((body, self.application.NAMESPACE_NOT_FOUND))

        if not namespace['publish'] and not self.application.INSECURE:
            raise Return((body, self.application.PERMISSION_DENIED))

        info = self.get_info(channel)

        result, error = yield self.application.process_publish(
            project,
            params,
            info=info
        )
        body["status"] = result
        raise Return((body, error))

    @coroutine
    def handle_presence(self, params):
        """
        Get presence information for channel.
        """
        project = self.application.get_project(self.project_name)
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))

        channel = params.get('channel')

        body = {
            "channel": channel,
        }

        self.check_channel_permission(channel)

        namespace = self.application.get_namespace(project, channel)
        if not namespace:
            raise Return((body, self.application.NAMESPACE_NOT_FOUND))

        if not namespace['presence']:
            raise Return((body, self.application.NOT_AVAILABLE))

        data, error = yield self.application.process_presence(
            project,
            params
        )
        body["data"] = data
        raise Return((body, error))

    @coroutine
    def handle_history(self, params):
        """
        Get message history for channel.
        """
        project = self.application.get_project(self.project_name)
        if not project:
            raise Return((None, self.application.PROJECT_NOT_FOUND))

        channel = params.get('channel')

        body = {
            "channel": channel,
        }

        self.check_channel_permission(channel)

        namespace = self.application.get_namespace(project, channel)
        if not namespace:
            raise Return((body, self.application.NAMESPACE_NOT_FOUND))

        if namespace['history_size'] <= 0 or namespace['history_lifetime'] <= 0:
            raise Return((body, self.application.NOT_AVAILABLE))

        data, error = yield self.application.process_history(
            project,
            params
        )
        body["data"] = data
        raise Return((body, error))

    def send_join_leave_message(self, channel, message_method):
        """
        Generate and send message about join or leave event.
        """
        subscription_key = self.application.engine.get_subscription_key(
            self.project_name, channel
        )
        info = self.get_info(channel)
        message = {
            "channel": channel,
            "data": info
        }
        self.application.engine.publish_message(
            subscription_key, message, method=message_method
        )

    def send_join_message(self, channel):
        """
        Send join message to all channel subscribers when client
        subscribed on channel.
        """
        self.send_join_leave_message(channel, 'join')

    def send_leave_message(self, channel):
        """
        Send leave message to all channel subscribers when client
        unsubscribed from channel.
        """
        self.send_join_leave_message(channel, 'leave')

    @coroutine
    def send_disconnect_message(self, reason=None):
        """
        Send disconnect message - after receiving it proper client
        must close connection and do not reconnect.
        """
        reason = reason or "default"
        message_body = {
            "reason": reason
        }
        response = Response(method="disconnect", body=message_body)
        result, error = yield self.send(response.as_message())
        raise Return((result, error))
