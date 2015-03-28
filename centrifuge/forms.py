# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import re

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

