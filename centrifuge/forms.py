# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import re
from wtforms import TextField, IntegerField, BooleanField, validators
from centrifuge.utils import Form


# regex pattern to match project and namespace names
NAME_PATTERN = r'^[-a-zA-Z0-9_]{2,}$'

NAME_PATTERN_DESCRIPTION = 'must consist of letters, numbers, underscores or hyphens'

NAME_RE = re.compile(NAME_PATTERN)

# how many times we are trying to authorize subscription by default
DEFAULT_MAX_AUTH_ATTEMPTS = 5

# milliseconds, increment for back-off
DEFAULT_BACK_OFF_INTERVAL = 100

# milliseconds, max timeout between auth attempts
DEFAULT_BACK_OFF_MAX_TIMEOUT = 5000

# how many messages keep in channel history by default
DEFAULT_HISTORY_SIZE = 50

# how long in seconds we keep history in inactive channels (0 - forever until size is not exceeded)
DEFAULT_HISTORY_EXPIRE = 3600  # 1 hour by default

# seconds
DEFAULT_CONNECTION_LIFETIME = 3600

# seconds
DEFAULT_CONNECTION_CHECK_INTERVAL = 10


class ProjectMixin(object):

    BOOLEAN_FIELDS = ['connection_check']

    name = TextField(
        label='project name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="project name: {0}".format(NAME_PATTERN_DESCRIPTION)
    )

    display_name = TextField(
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
        description="check expired connections sending POST request to web application"
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

    connection_check_address = TextField(
        label='connection check url address',
        validators=[
            validators.URL(require_tld=False),
            validators.Optional()
        ],
        description="url address to check connections by periodically sending POST request "
                    "to it with list of users with expired connections. "
    )

    connection_check_interval = IntegerField(
        label='minimum connection check interval in seconds',
        validators=[
            validators.NumberRange(min=1)
        ],
        default=DEFAULT_CONNECTION_CHECK_INTERVAL,
        description="minimum time interval in seconds between periodic connection "
                    "check POST requests to your web application."
    )

    max_auth_attempts = IntegerField(
        label='maximum auth attempts',
        validators=[
            validators.NumberRange(min=1, max=100)
        ],
        default=DEFAULT_MAX_AUTH_ATTEMPTS,
        description="maximum amount of POST requests from Centrifuge to your application "
                    "during client's authorization"
    )

    back_off_interval = IntegerField(
        label='back-off interval',
        validators=[
            validators.NumberRange(min=50, max=10000)
        ],
        default=DEFAULT_BACK_OFF_INTERVAL,
        description="interval increment in milliseconds in authorization back-off mechanism. "
                    "Please, keep it default until you know what you do"
    )

    back_off_max_timeout = IntegerField(
        label='back-off max timeout',
        validators=[
            validators.NumberRange(min=50, max=120000)
        ],
        default=DEFAULT_BACK_OFF_MAX_TIMEOUT,
        description="maximum interval in milliseconds between authorization requests. "
                    "Please, keep it default until you know what you do"
    )


class NamespaceMixin(object):

    BOOLEAN_FIELDS = [
        'is_watching', 'is_private', 'publish',
        'presence', 'history', 'join_leave', 'anonymous'
    ]

    is_watching = BooleanField(
        label='is watching',
        validators=[],
        default=True,
        description="publish messages into admin channel "
                    "(messages will be visible in web interface). Turn it off "
                    "if you expect high load in channels."
    )

    is_private = BooleanField(
        label='is private',
        validators=[],
        default=False,
        description="authorize every subscription on channel using "
                    "POST request to provided auth address (see below)"
    )

    auth_address = TextField(
        label='auth url address',
        validators=[
            validators.URL(require_tld=False),
            validators.Optional()
        ],
        description="url address to authorize clients sending POST request to it"
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
                    "do not expire at all - not recommended though as this can lead to"
                    "memory leaks (as Centrifuge keeps all history in memory), default "
                    "is 86400 seconds (24 hours)"
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


class NamespaceNameMixin(object):

    name = TextField(
        label='namespace name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="unique namespace name: {0}".format(NAME_PATTERN_DESCRIPTION)
    )


class NamespaceForm(NamespaceNameMixin, NamespaceMixin, Form):

    field_order = ('name', '*')
