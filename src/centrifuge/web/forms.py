# coding: utf-8
import re
from wtforms import TextField, IntegerField, BooleanField, validators
from ..utils import Form


# regex pattern to match project and category names
NAME_RE = re.compile('^[^_]+[A-z0-9]{2,}$')

DEFAULT_MAX_AUTH_ATTEMPTS = 5

# milliseconds
DEFAULT_BACK_OFF_INTERVAL = 100

# milliseconds
DEFAULT_BACK_OFF_MAX_TIMEOUT = 5000

# seconds
DEFAULT_PRESENCE_PING_INTERVAL = 25

# seconds
DEFAULT_PRESENCE_EXPIRE_INTERVAL = 60

DEFAULT_HISTORY_SIZE = 20


class ProjectForm(Form):

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
            validators.URL(),
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
        description="bidirectional categories allow clients to publish messages in channels"
    )

    is_monitored = BooleanField(
        label='is monitored',
        validators=[],
        default=False,
        description="publish all category channel's messages to administrator's web interface"
    )

    presence = BooleanField(
        label='presence information',
        validators=[],
        default=True,
        description="check if you want to get presence info for channels in this category"
    )

    presence_ping_interval = IntegerField(
        label='presence ping interval in seconds',
        validators=[
            validators.NumberRange(min=1)
        ],
        description="client's presence ping interval (internal)",
        default=DEFAULT_PRESENCE_PING_INTERVAL
    )

    presence_expire_interval = IntegerField(
        label="presence expire interval in seconds",
        validators=[
            validators.NumberRange(min=2)
        ],
        description="how long we must consider presence info valid after receiving presence ping",
        default=DEFAULT_PRESENCE_EXPIRE_INTERVAL
    )

    history = BooleanField(
        label='history information',
        validators=[],
        default=True,
        description="check if you want to get history info for channels in this category"
    )

    history_size = IntegerField(
        label="history size",
        validators=[
            validators.NumberRange(min=1)
        ],
        default=DEFAULT_HISTORY_SIZE,
        description="maximum amount of messages in history for channels in this category"
    )
