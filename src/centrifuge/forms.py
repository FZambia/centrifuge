# coding: utf-8
#
# Copyright (c) Alexandr Emelin. MIT license.
# All rights reserved.

import re
from wtforms import TextField, IntegerField, BooleanField, validators
from centrifuge.utils import Form


# regex pattern to match project and namespace names
NAME_RE = re.compile('^[^_]+[A-z0-9@\-_\.]{2,}$')

# how many times we are trying to authorize subscription by default
DEFAULT_MAX_AUTH_ATTEMPTS = 5

# milliseconds, increment for back-off
DEFAULT_BACK_OFF_INTERVAL = 100

# milliseconds, max timeout between auth attempts
DEFAULT_BACK_OFF_MAX_TIMEOUT = 5000

# how many messages keep in channel history by default
DEFAULT_HISTORY_SIZE = 20


class ProjectMixin(object):

    BOOLEAN_FIELDS = []

    name = TextField(
        label='project name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="project name, must contain ascii symbols only"
    )

    display_name = TextField(
        label='display name',
        validators=[
            validators.Length(min=3, max=50),
            validators.Optional()
        ],
        description="human readable project name, will be used in web interface"
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
        label='back-off interval in milliseconds',
        validators=[
            validators.NumberRange(min=50, max=10000)
        ],
        default=DEFAULT_BACK_OFF_INTERVAL,
        description="please, keep it default until you know what you do"
    )

    back_off_max_timeout = IntegerField(
        label='back-off max timeout in milliseconds',
        validators=[
            validators.NumberRange(min=50, max=120000)
        ],
        default=DEFAULT_BACK_OFF_MAX_TIMEOUT,
        description="please, keep it default until you know what you do"
    )


class NamespaceMixin(object):

    BOOLEAN_FIELDS = [
        'is_watching', 'is_private', 'publish',
        'presence', 'history', 'join_leave'
    ]

    is_watching = BooleanField(
        label='is watching',
        validators=[],
        default=False,
        description="publish messages into admin channel "
                    "(messages will be visible in web interface)"
    )

    is_private = BooleanField(
        label='is private',
        validators=[],
        default=False,
        description="authorize every subscription on channel using "
                    "POST request to auth address"
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

    presence = BooleanField(
        label='presence',
        validators=[],
        default=True,
        description="enable presence information for channels "
                    "(state must be configured)"
    )

    history = BooleanField(
        label='history',
        validators=[],
        default=True,
        description="enable history information for channels "
                    "(state must be configured)"
    )

    history_size = IntegerField(
        label="history size",
        validators=[
            validators.NumberRange(min=1)
        ],
        default=DEFAULT_HISTORY_SIZE,
        description="maximum amount of messages in history for channels"
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
        description="unique namespace name, ascii symbols only"
    )


class NamespaceForm(NamespaceNameMixin, NamespaceMixin, Form):

    field_order = ('name', '*')
