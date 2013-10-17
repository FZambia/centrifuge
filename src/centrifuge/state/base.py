# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import time
from tornado.gen import coroutine, Return
from six import iteritems


class BaseState(object):
    """
    In memory state storage. Suitable for using with single Centrifuge instance only.
    """

    def __init__(self, application, io_loop=None, fake=False, presence_timeout=60, history_size=20):
        self.application = application
        self.io_loop = io_loop
        self.fake = fake
        self.presence_timeout = presence_timeout
        self.history_size = history_size
        self.presence = {}
        self.history = {}

    def initialize(self):
        pass

    @staticmethod
    def get_presence_hash_key(project_id, namespace, channel):
        return "centrifuge:presence:hash:%s:%s:%s" % (project_id, namespace, channel)

    @staticmethod
    def get_history_list_key(project_id, namespace, channel):
        return "centrifuge:history:%s:%s:%s" % (project_id, namespace, channel)

    @coroutine
    def add_presence(self, project_id, namespace, channel, uid, user_info, presence_timeout=None):
        """
        Add user's presence with appropriate expiration time.
        Must be called when user subscribes on channel.
        """
        if self.fake:
            raise Return((True, None))

        now = int(time.time())
        expire_at = now + (presence_timeout or self.presence_timeout)

        hash_key = self.get_presence_hash_key(project_id, namespace, channel)

        if hash_key not in self.presence:
            self.presence[hash_key] = {}

        self.presence[hash_key][uid] = {
            'expire_at': expire_at,
            'user_info': user_info
        }

        raise Return((True, None))

    @coroutine
    def remove_presence(self, project_id, namespace, channel, uid):
        """
        Remove user's presence.
        Must be called on disconnects of any kind.
        """
        if self.fake:
            raise Return((True, None))
        hash_key = self.get_presence_hash_key(project_id, namespace, channel)
        try:
            del self.presence[hash_key][uid]
        except KeyError:
            pass

        raise Return((True, None))

    @coroutine
    def get_presence(self, project_id, namespace, channel):
        """
        Get presence for channel.
        """
        if self.fake:
            raise Return((None, None))

        now = int(time.time())

        hash_key = self.get_presence_hash_key(project_id, namespace, channel)

        to_return = {}
        if hash_key in self.presence:
            keys_to_delete = []
            for uid, data in iteritems(self.presence[hash_key]):
                expire_at = data['expire_at']
                if expire_at > now:
                    to_return[uid] = data['user_info']
                else:
                    keys_to_delete.append(uid)

            for uid in keys_to_delete:
                try:
                    del self.presence[hash_key][uid]
                except KeyError:
                    pass

            if not self.presence[hash_key]:
                try:
                    del self.presence[hash_key]
                except KeyError:
                    pass

        raise Return((to_return, None))

    @coroutine
    def add_history_message(self, project_id, namespace, channel, message, history_size=None):
        """
        Add message to channel's history.
        Must be called when new message has been published.
        """
        if self.fake:
            raise Return((True, None))

        history_list_key = self.get_history_list_key(project_id, namespace, channel)

        if history_list_key not in self.history:
            self.history[history_list_key] = []

        history_size = history_size or self.history_size

        self.history[history_list_key].insert(0, message)
        self.history[history_list_key] = self.history[history_list_key][:history_size]

        raise Return((True, None))

    @coroutine
    def get_history(self, project_id, namespace, channel):
        """
        Get a list of last messages for channel.
        """
        if self.fake:
            raise Return((None, None))

        history_list_key = self.get_history_list_key(project_id, namespace, channel)

        try:
            data = self.history[history_list_key]
        except KeyError:
            data = []

        raise Return((data, None))
