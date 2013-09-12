# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import re
from wtforms import TextField, IntegerField, BooleanField, validators, SelectField
from ..utils import Form


# regex pattern to match project and namespace names
NAME_RE = re.compile('^[^_]+[A-z0-9]{2,}$')

DEFAULT_MAX_AUTH_ATTEMPTS = 5

# milliseconds
DEFAULT_BACK_OFF_INTERVAL = 100

# milliseconds
DEFAULT_BACK_OFF_MAX_TIMEOUT = 5000


DEFAULT_HISTORY_SIZE = 20


class ProjectForm(Form):

    def __init__(self, *args, **kwargs):
        super(ProjectForm, self).__init__(*args, **kwargs)
        namespace_choices = kwargs.get('namespace_choices', None)
        if namespace_choices:
            self.default_namespace.choices = namespace_choices
        else:
            del self.default_namespace

    name = TextField(
        label='project name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="unique project name, must contain ascii symbols only"
    )

    display_name = TextField(
        label='display name',
        validators=[
            validators.Length(min=3, max=50)
        ],
        description="human readable project name"
    )

    auth_address = TextField(
        label='auth url address',
        validators=[
            validators.URL(require_tld=False),
            validators.Optional()
        ],
        description="url address to authorize clients"
    )

    max_auth_attempts = IntegerField(
        label='maximum auth attempts',
        validators=[
            validators.NumberRange(min=1, max=100)
        ],
        default=DEFAULT_MAX_AUTH_ATTEMPTS,
        description="maximum amount of requests from Centrifuge to application during client's authorization"
    )

    back_off_interval = IntegerField(
        label='back-off interval in milliseconds',
        validators=[
            validators.NumberRange(min=50, max=10000)
        ],
        default=DEFAULT_BACK_OFF_INTERVAL,
        description="internal, keep it default until you know what you want"
    )

    back_off_max_timeout = IntegerField(
        label='back-off max timeout in milliseconds',
        validators=[
            validators.NumberRange(min=50, max=120000)
        ],
        default=DEFAULT_BACK_OFF_MAX_TIMEOUT,
        description="internal, keep it default until you know what you want"
    )

    default_namespace = SelectField(
        label='default namespace',
        validators=[],
        default=None
    )

    def validate_name(self, field):
        field.data = field.data.lower()


class NamespaceForm(Form):

    name = TextField(
        label='namespace name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="unique namespace name"
    )

    is_watching = BooleanField(
        label='is watching',
        validators=[],
        default=False,
        description="publish all namespace channel's messages to administrator's web interface"
    )

    is_private = BooleanField(
        label='is private',
        validators=[],
        default=False,
        description="authorize every subscription request using auth address"
    )

    publish = BooleanField(
        label='publish',
        validators=[],
        default=False,
        description="allow clients to publish messages in channels"
    )

    presence = BooleanField(
        label='presence',
        validators=[],
        default=True,
        description="check if you want to get presence info for channels in this namespace"
    )

    history = BooleanField(
        label='history',
        validators=[],
        default=True,
        description="check if you want to get history info for channels in this namespace"
    )

    history_size = IntegerField(
        label="history size",
        validators=[
            validators.NumberRange(min=1)
        ],
        default=DEFAULT_HISTORY_SIZE,
        description="maximum amount of messages in history for channels in this namespace"
    )

    join_leave = BooleanField(
        label="join/leave messages",
        validators=[],
        default=True,
        description="send join(leave) messages when client subscribes on channel "
                    "(unsubscribes from channel)"
    )

    auth_address = TextField(
        label='auth url address',
        validators=[
            validators.URL(require_tld=False),
            validators.Optional()
        ],
        description="url address to authorize clients specific for namespace "
                    "(leave it blank to use auth url from project)"
    )
