# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import logging
from tornado.log import LogFormatter


handler = logging.StreamHandler()
handler.setFormatter(LogFormatter())
logger = logging.getLogger('centrifuge')
logger.setLevel(logging.DEBUG)
logger.addHandler(handler)

logger.propagate = False

# hook up tornado 3's loggers to our app handlers
for name in ('access', 'application', 'general'):
    logging.getLogger('tornado.%s' % name).handlers = logger.handlers
    logging.getLogger('tornado.%s' % name).propagate = False