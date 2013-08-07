# coding: utf-8
import re
from wtforms import TextField, IntegerField, BooleanField, validators
from ..utils import Form


# regex pattern to match project and category names
NAME_RE = re.compile('^[^_]+[A-z0-9]{2,}$')

DEFAULT_MAX_AUTH_ATTEMPTS = 5

DEFAULT_BACK_OFF_INTERVAL = 100

DEFAULT_BACK_OFF_MAX_TIMEOUT = 5000


class ProjectForm(Form):

    name = TextField(
        label='project name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="unique project name"
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
            validators.URL(),
            validators.Optional()
        ],
        description="url address to authorize clients"
    )

    max_auth_attempts = IntegerField(
        label='maximum auth attempts',
        validators=[
            validators.Optional(),
            validators.NumberRange(min=1, max=100)
        ],
        default=DEFAULT_MAX_AUTH_ATTEMPTS
    )

    back_off_interval = IntegerField(
        label='back-off interval in milliseconds',
        validators=[
            validators.Optional(),
            validators.NumberRange(min=50, max=10000)
        ],
        default=DEFAULT_BACK_OFF_INTERVAL
    )

    back_off_max_timeout = IntegerField(
        label='back-off max timeout in milliseconds',
        validators=[
            validators.Optional(),
            validators.NumberRange(min=50, max=120000)
        ],
        default=DEFAULT_BACK_OFF_MAX_TIMEOUT
    )

    def validate_name(self, field):
        field.data = field.data.lower()


class CategoryForm(Form):

    name = TextField(
        label='category name',
        validators=[
            validators.Regexp(regex=NAME_RE, message="invalid name")
        ],
        description="unique category name"
    )

    is_bidirectional = BooleanField(
        label='is bidirectional',
        validators=[],
        default=False,
        description="bidirectional categories allow clients to publish messages"
    )

    is_monitored = BooleanField(
        label='is monitored',
        validators=[],
        default=False,
        description="publish all messages to special administrative channels"
    )

    presence = BooleanField(
        label=''
    )

    presence_timeout = TextField