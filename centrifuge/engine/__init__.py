# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

from tornado.ioloop import IOLoop
from tornado.gen import coroutine, Return


class BaseEngine(object):
    """
    This is base interface for all engines.

    Most of its coroutine methods should be implemented in actual engine class.

    There three main components - PUB/SUB logic to connect Centrifuge instances, presence
    logic to maintain actual presence information for channels and history logic to control
    channel history.
    """

    CHANNEL_PREFIX = 'centrifuge'

    # channel for administrative web interface.
    ADMIN_CHANNEL = 'admin'

    # channel for sharing commands among all nodes.
    CONTROL_CHANNEL = 'control'

    # in seconds, how often connected clients must send presence info to state storage
    DEFAULT_PRESENCE_PING_INTERVAL = 25

    # in seconds, how long we must consider presence info valid after
    # receiving presence ping
    DEFAULT_PRESENCE_EXPIRE_INTERVAL = 60

    NAME = 'Base engine'

    def __init__(self, application, io_loop=None):
        self.application = application
        self.io_loop = io_loop or IOLoop.instance()
        self.config = self.application.settings.get("config", {})
        self.options = self.application.settings.get('options')

        self.prefix = self.config.get('channel_prefix', self.CHANNEL_PREFIX)
        self.admin_channel_name = "{0}.{1}".format(self.prefix, "admin")
        self.control_channel_name = "{0}.{1}".format(self.prefix, "control")

        self.presence_ping_interval = self.config.get(
            'presence_ping_interval',
            self.DEFAULT_PRESENCE_PING_INTERVAL
        )*1000

        self.presence_timeout = self.config.get(
            "presence_expire_interval",
            self.DEFAULT_PRESENCE_EXPIRE_INTERVAL
        )

    def initialize(self):
        """
        Put engine specific initialization logic here. At this moment IO LOOP already started.
        """
        pass

    def get_subscription_key(self, project_key, channel):
        """
        Create subscription name to catch messages from specific project and channel.
        """
        return ".".join([self.prefix, project_key, channel])

    @coroutine
    def publish_message(self, channel, body, method="message"):
        """
        Send message with body into channel with specified method.
        """
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
    def add_subscription(self, project_key, channel, client):
        """
        Subscribe application on channel if necessary and register client
        to receive messages from that channel.
        """
        raise Return((True, None))

    @coroutine
    def remove_subscription(self, project_key, channel, client):
        """
        Unsubscribe application from channel if necessary and prevent client
        from receiving messages from that channel.
        """
        raise Return((True, None))

    @coroutine
    def add_presence(self, project_key, channel, uid, user_info, presence_timeout=None):
        """
        Add (or update) presence information when client subscribed on channel
        (or still in channel) in project.
        """
        raise Return((True, None))

    @coroutine
    def remove_presence(self, project_key, channel, uid):
        """
        Remove presence information when client unsubscribed from channel in project.
        """
        raise Return((True, None))

    @coroutine
    def get_presence(self, project_key, channel):
        """
        Get presence information for channel in project.
        """
        raise Return((None, None))

    @coroutine
    def add_history_message(self, project_key, channel, message, history_size, history_lifetime):
        """
        Add new history message for channel, trim history if needed.
        """
        raise Return((True, None))

    @coroutine
    def get_history(self, project_key, channel):
        """
        Return history messages for channel in project.
        """
        raise Return((None, None))
