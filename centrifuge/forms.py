# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import re
from wtforms import StringField, IntegerField, BooleanField, validators
from centrifuge.utils import Form


# regex pattern to match project and namespace names
NAME_PATTERN = r'^[-a-zA-Z0-9_]{2,}$'

NAME_PATTERN_DESCRIPTION = 'must consist of letters, numbers, underscores or hyphens'

NAME_RE = re.compile(NAME_PATTERN)

# how many messages keep in channel history by default
DEFAULT_HISTORY_SIZE = 50

# in seconds how long we keep history in inactive channels (0 - forever until size is not exceeded)
DEFAULT_HISTORY_EXPIRE = 3600  # 1 hour by default

# in seconds
DEFAULT_CONNECTION_LIFETIME = 3600


class ProjectMixin(object):

    BOOLEAN_FIELDS = ['connection_check']

    name = StringField(
        label='project name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="project name: {0}".format(NAME_PATTERN_DESCRIPTION)
    )

    display_name = StringField(
        label='display name',
        validators=[
            validators.Length(min=3, max=50),
            validators.Optional()
        ],
        description="human readable project name, will be used in web interface"
    )

    connection_check = BooleanField(
        label='connection check',
        validators=[],
        default=False,
        description="check expired connections"
    )

    connection_lifetime = IntegerField(
        label='connection lifetime in seconds',
        validators=[
            validators.NumberRange(min=1)
        ],
        default=DEFAULT_CONNECTION_LIFETIME,
        description="time interval in seconds for connection to expire. Keep it as large "
                    "as possible in your case."
    )


class NamespaceNameMixin(object):

    name = StringField(
        label='namespace name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="unique namespace name: {0}".format(NAME_PATTERN_DESCRIPTION)
    )


class NamespaceMixin(object):

    BOOLEAN_FIELDS = [
        'is_watching', 'publish', 'presence',
        'history', 'join_leave', 'anonymous'
    ]

    is_watching = BooleanField(
        label='is watching',
        validators=[],
        default=True,
        description="publish messages into admin channel "
                    "(messages will be visible in web interface). Turn it off "
                    "if you expect high load in channels."
    )

    publish = BooleanField(
        label='publish',
        validators=[],
        default=False,
        description="allow clients to publish messages in channels "
                    "(your web application never receive those messages)"
    )

    anonymous = BooleanField(
        label='anonymous access',
        validators=[],
        default=False,
        description="allow anonymous (with empty USER ID) clients to subscribe on channels"
    )

    presence = BooleanField(
        label='presence',
        validators=[],
        default=True,
        description="enable presence information for channels"
    )

    history = BooleanField(
        label='history',
        validators=[],
        default=False,
        description="enable history information for channels "
                    "(messages will be kept in process memory or in Redis depending on engine used)"
    )

    history_size = IntegerField(
        label="history size",
        validators=[
            validators.NumberRange(min=1)
        ],
        default=DEFAULT_HISTORY_SIZE,
        description="maximum amount of messages in history for single channel"
    )

    history_expire = IntegerField(
        label="history expire",
        validators=[
            validators.NumberRange(min=0)
        ],
        default=DEFAULT_HISTORY_EXPIRE,
        description="time in seconds to keep history for inactive channels. 0 - "
                    "do not expire at all - not recommended though as this can lead to "
                    "memory leaks (as Centrifuge keeps all history in memory)"
    )

    join_leave = BooleanField(
        label="join/leave messages",
        validators=[],
        default=True,
        description="send join(leave) messages when client subscribes on channel "
                    "(unsubscribes from channel)"
    )


class ProjectForm(ProjectMixin, NamespaceMixin, Form):

    BOOLEAN_FIELDS = ProjectMixin.BOOLEAN_FIELDS + NamespaceMixin.BOOLEAN_FIELDS


class NamespaceForm(NamespaceNameMixin, NamespaceMixin, Form):

    pass
