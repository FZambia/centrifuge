# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import os
import sys
import json
import tornado
import tornado.web
import tornado.ioloop
import tornado.options
import tornado.httpserver
from tornado.options import define, options


define(
    "debug", default=False, help="tornado debug mode", type=bool
)

define(
    "port", default=8000, help="app port", type=int
)

define(
    "zmq_pub_listen", default="127.0.0.1", help="zmq pub listen", type=str
)

define(
    "zmq_pub_port", default=7000, help="zmq pub port", type=int
)

define(
    "zmq_pub_port_shift", default=None, type=int,
    help="zmq port shift with respect to tornado port (useful "
         "when deploying with supervisor on one machine)"
)

define(
    "zmq_sub_address", default=["tcp://localhost:7000"], type=str, multiple=True,
    help="comma-separated list of all ZeroMQ PUB socket addresses"
)

define(
    "zmq_pub_sub_proxy", default=False, type=bool, help="use XPUB/XSUB proxy"
)

define(
    "zmq_xsub", default="tcp://localhost:6000", type=str, help="XSUB socket address"
)

define(
    "zmq_xpub", default="tcp://localhost:6001", type=str, help="XPUB socket address"
)

define(
    "base", default=False, help="use Base PUB/SUB (single node compatible only)", type=bool
)

define(
    "redis", default=False, help="use Redis for PUB/SUB", type=bool
)

define(
    "redis_host", default="localhost", help="Redis host", type=str
)

define(
    "redis_port", default=6379, help="Redis port", type=int
)

define(
    "redis_db", default=0, help="Redis database number", type=int
)

define(
    "config", default='config.json', help="JSON config file", type=str
)


tornado.options.parse_command_line()


if not options.redis and not options.base:

    from zmq.eventloop import ioloop

    # Install ZMQ ioloop instead of a tornado ioloop
    # http://zeromq.github.com/pyzmq/eventloop.html
    ioloop.install()

from centrifuge.log import logger
from centrifuge.core import Application

from sockjs.tornado import SockJSRouter

from centrifuge.handlers import ApiHandler
from centrifuge.handlers import SockjsConnection
from centrifuge.handlers import Client

from centrifuge.web.handlers import MainHandler
from centrifuge.web.handlers import AuthHandler
from centrifuge.web.handlers import LogoutHandler
from centrifuge.web.handlers import AdminSocketHandler
from centrifuge.web.handlers import Http404Handler
from centrifuge.web.handlers import ProjectCreateHandler
from centrifuge.web.handlers import NamespaceFormHandler
from centrifuge.web.handlers import ProjectSettingsHandler
from centrifuge.web.handlers import StructureDumpHandler


def stop_running(msg):
    """
    Called only during initialization when critical error occurred.
    """
    logger.error(msg)
    sys.exit(1)


def create_application_handlers(sockjs_settings):

    handlers = [
        tornado.web.url(
            r'/', MainHandler, name="main"
        ),
        tornado.web.url(
            r'/project/create$',
            ProjectCreateHandler,
            name="project_create"
        ),
        tornado.web.url(
            r'/project/([^/]+)/settings/([^/]+)$',
            ProjectSettingsHandler,
            name="project_settings"
        ),
        tornado.web.url(
            r'/project/([^/]+)/namespace/create$',
            NamespaceFormHandler,
            name="namespace_create"
        ),
        tornado.web.url(
            r'/project/([^/]+)/namespace/edit/([^/]+)/',
            NamespaceFormHandler,
            name="namespace_edit"
        ),
        tornado.web.url(
            r'/api/([^/]+)$', ApiHandler, name="api"
        ),
        tornado.web.url(
            r'/auth$', AuthHandler, name="auth"
        ),
        tornado.web.url(
            r'/logout$', LogoutHandler, name="logout"
        ),
        tornado.web.url(
            r'/dumps$', StructureDumpHandler, name="dump_structure"
        )
    ]

    # create SockJS route for admin connections
    admin_sock_router = SockJSRouter(
        AdminSocketHandler, '/socket', user_settings=sockjs_settings
    )
    handlers = admin_sock_router.urls + handlers

    # create SockJS route for client connections
    client_sock_router = SockJSRouter(
        SockjsConnection, '/connection', user_settings=sockjs_settings
    )
    handlers = client_sock_router.urls + handlers

    # match everything else to 404 handler
    handlers.append(
        tornado.web.url(
            r'.*', Http404Handler, name='http404'
        )
    )

    return handlers


def main():

    # load settings from configuration file
    try:
        custom_settings = json.load(open(options.config, 'r'))
    except IOError:
        logger.warning(
            "Application started without configuration file.\n"
            "This is normal only during development"
        )
        custom_settings = {}

    ioloop_instance = tornado.ioloop.IOLoop.instance()

    settings = dict(
        cookie_secret=custom_settings.get("cookie_secret", "bad secret"),
        login_url="/auth",
        template_path=os.path.join(
            os.path.dirname(__file__),
            os.path.join("web/frontend", "templates")
        ),
        static_path=os.path.join(
            os.path.dirname(__file__),
            os.path.join("web/frontend", "static")
        ),
        xsrf_cookies=True,
        autoescape="xhtml_escape",
        debug=options.debug,
        options=options,
        config=custom_settings
    )

    sockjs_settings = custom_settings.get("sockjs_settings", {})

    handlers = create_application_handlers(sockjs_settings)

    try:
        app = Application(handlers=handlers, **settings)
        server = tornado.httpserver.HTTPServer(app)
        server.listen(options.port)
    except Exception as e:
        return stop_running(str(e))

    # create references to application from SockJS handlers
    AdminSocketHandler.application = app
    Client.application = app

    # choose PUB/SUB mechanism
    if options.base:
        from centrifuge.pubsub.base import BasePubSub as PubSub
    elif options.redis:
        from centrifuge.pubsub.redis import PubSub
    else:
        from centrifuge.pubsub.zeromq import PubSub

    app.pubsub = PubSub(app)

    app.initialize()

    magic_project_id = custom_settings.get('magic_project_id')
    if magic_project_id:
        app.MAGIC_PROJECT_ID = magic_project_id

    magic_project_param = custom_settings.get('magic_project_param')
    if magic_project_param:
        app.MAGIC_PROJECT_PARAM = magic_project_param

    logger.info("Tornado port: {0}".format(options.port))

    # finally, let's go
    try:
        ioloop_instance.start()
    except KeyboardInterrupt:
        logger.info('interrupted')
    finally:
        # cleaning
        if hasattr(app.pubsub, 'clean'):
            app.pubsub.clean()


if __name__ == '__main__':
    main()
