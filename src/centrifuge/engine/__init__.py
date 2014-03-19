# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

from tornado.ioloop import IOLoop
from tornado.gen import coroutine, Return


class BaseEngine(object):

    PREFIX = 'centrifuge'

    # separator to join parts of channel name
    PART_DELIMITER = "|"

    # channel for administrative web interface.
    ADMIN_CHANNEL = '_admin'

    # channel for sharing commands among all nodes.
    CONTROL_CHANNEL = '_control'

    # in seconds, how often connected clients must send presence info to state storage
    DEFAULT_PRESENCE_PING_INTERVAL = 25

    # in seconds, how long we must consider presence info valid after
    # receiving presence ping
    DEFAULT_PRESENCE_EXPIRE_INTERVAL = 60

    # how many messages keep in history for channel by default
    DEFAULT_HISTORY_SIZE = 20

    DEFAULT_PUBLISH_METHOD = 'message'

    NAME = 'Base engine'

    def __init__(self, application, io_loop=None):
        self.application = application
        self.io_loop = io_loop or IOLoop.instance()
        self.config = self.application.settings.get("config", {})
        self.options = self.application.settings.get('options')

        self.prefix = self.config.get(
            'engine_prefix', self.PREFIX
        )

        self.admin_channel_name = self.config.get(
            'engine_admin_channel_name', self.ADMIN_CHANNEL
        )

        self.control_channel_name = self.config.get(
            'engine_control_channel_name', self.CONTROL_CHANNEL
        )

        self.part_delimiter = self.config.get(
            'engine_part_delimiter', self.PART_DELIMITER
        )

        self.presence_ping_interval = self.config.get(
            'engine_presence_ping_interval',
            self.DEFAULT_PRESENCE_PING_INTERVAL
        )*1000

        self.presence_timeout = self.config.get(
            "engine_presence_expire_interval",
            self.DEFAULT_PRESENCE_EXPIRE_INTERVAL
        )

        self.history_size = self.config.get(
            "engine_history_size",
            self.DEFAULT_HISTORY_SIZE
        )

    def initialize(self):
        pass

    def get_subscription_key(self, project_id, channel):
        """
        Create subscription name to catch messages from specific project and channel.
        """
        return self.PART_DELIMITER.join([self.prefix, project_id, channel])

    @coroutine
    def publish_message(self, channel, body, method=DEFAULT_PUBLISH_METHOD):
        raise Return((True, None))

    @coroutine
    def publish_control_message(self, message):
        """
        Send message to control channel.
        This channel for sharing commands between running instances.
        """
        raise Return((True, None))

    @coroutine
    def publish_admin_message(self, message):
        """
        Send message to admin channel.
        This channel for sending events to administrative interface.
        """
        raise Return((True, None))

    @coroutine
    def add_subscription(self, project_id, channel, client):
        raise Return((True, None))

    @coroutine
    def remove_subscription(self, project_id, channel, client):
        raise Return((True, None))

    @coroutine
    def add_presence(self, project_id, channel, uid, user_info, presence_timeout=None):
        raise Return((True, None))

    @coroutine
    def remove_presence(self, project_id, channel, uid):
        raise Return((True, None))

    @coroutine
    def get_presence(self, project_id, channel):
        raise Return((None, None))

    @coroutine
    def add_history_message(self, project_id, channel, message, history_size=None):
        raise Return((True, None))

    @coroutine
    def get_history(self, project_id, channel):
        raise Return((None, None))
