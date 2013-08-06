import toredis
import time
from tornado.gen import coroutine, Return, Task
from six import PY3


if PY3:
    range_func = range
else:
    range_func = xrange


def dict_from_list(key_value_list):
    return dict(key_value_list[i:i+2] for i in range_func(0, len(key_value_list), 2))


class State(object):

    def __init__(self, host="localhost", port=6379, io_loop=None, presence_timeout=60, history_size=20):
        self.host = host
        self.port = port
        self.io_loop = io_loop
        self.connected = False
        self.presence_timeout = presence_timeout
        self.history_size = history_size
        self.client = toredis.Client(io_loop=self.io_loop)
        self.client.connect()

    def get_presence_hash_key(self, project_id, category, channel):
        return "presence:hash:%s:%s:%s" % (project_id, category, channel)

    def get_presence_set_key(self, project_id, category, channel):
        return "presence:set:%s:%s:%s" % (project_id, category, channel)

    def get_history_list_key(self, project_id, category, channel):
        return "history:%s:%s:%s" % (project_id, category, channel)

    @coroutine
    def add_presence(self, project_id, category, channel, user_id, user_info=None):
        """
        Add user's presence with appropriate expiration time.
        Must be called when user subscribes on channel.
        """
        now = int(time.time())
        expire_at = now + self.presence_timeout
        hash_key = self.get_presence_hash_key(project_id, category, channel)
        set_key = self.get_presence_set_key(project_id, category, channel)
        yield Task(self.client.zadd, set_key, {user_id: expire_at})
        yield Task(self.client.hset, hash_key, user_id, user_info or '')
        raise Return((True, None))

    @coroutine
    def remove_presence(self, project_id, category, channel, user_id):
        """
        Remove user's presence from Redis.
        Must be called on disconnects of any kind.
        """
        hash_key = self.get_presence_hash_key(project_id, category, channel)
        set_key = self.get_presence_set_key(project_id, category, channel)
        yield Task(self.client.hdel, hash_key, user_id)
        yield Task(self.client.zrem, set_key, user_id)
        raise Return((True, None))

    @coroutine
    def get_presence(self, project_id, category, channel):
        """
        Get presence for channel.
        """
        now = int(time.time())
        hash_key = self.get_presence_hash_key(project_id, category, channel)
        set_key = self.get_presence_set_key(project_id, category, channel)
        expired_keys = yield Task(self.client.zrangebyscore, set_key, 0, now)
        if expired_keys:
            yield Task(self.client.zremrangebyscore, set_key, 0, now)
            yield Task(self.client.hdel, hash_key, expired_keys)
        data = yield Task(self.client.hgetall, hash_key)
        raise Return((dict_from_list(data), None))

    @coroutine
    def add_history_message(self, project_id, category, channel, message, history_size=None):
        """
        Add message to channel's history.
        Must be called when new message has been published.
        """
        history_size = history_size or self.history_size
        list_key = self.get_history_list_key(project_id, category, channel)
        yield Task(self.client.lpush, list_key, message)
        yield Task(self.client.ltrim, list_key, 0, history_size - 1)
        raise Return((True, None))

    @coroutine
    def get_history(self, project_id, category, channel):
        """
        Get a list of last messages for channel.
        """
        history_list_key = self.get_history_list_key(project_id, category, channel)
        data = yield Task(self.client.lrange, history_list_key, 0, -1)
        raise Return((data, None))
