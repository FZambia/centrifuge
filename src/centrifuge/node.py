# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.

import os
import sys
import json
import tornado
import tornado.web
import tornado.httpserver
import tornado.ioloop
import tornado.options
from tornado.options import define, options
from sockjs.tornado import SockJSRouter

from zmq.eventloop import ioloop


# Install ZMQ ioloop instead of a tornado ioloop
# http://zeromq.github.com/pyzmq/eventloop.html
ioloop.install()

from centrifuge.core import Application
from centrifuge.log import logger

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
    "zmq_xsub", default="tcp://localhost:6000", type=str,
    help="XSUB socket address"
)

define(
    "zmq_xpub", default="tcp://localhost:6001", type=str,
    help="XPUB socket address"
)

define(
    "config", default='config.json', help="JSON config file", type=str
)


def stop_running(msg):
    """
    Called only during initialization when critical error occurred.
    """
    logger.error(msg)
    sys.exit(1)


def create_application_handlers():

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
        )
    ]

    # create SockJS route for admin connections
    AdminConnectionRouter = SockJSRouter(
        AdminSocketHandler, '/socket'
    )
    handlers = AdminConnectionRouter.urls + handlers

    # create SockJS route for client connections
    SockjsConnectionRouter = SockJSRouter(
        SockjsConnection, '/connection'
    )
    handlers = SockjsConnectionRouter.urls + handlers

    # match everything else to 404 handler
    handlers.append(
        tornado.web.url(
            r'.*', Http404Handler, name='http404'
        )
    )

    return handlers


def main():

    tornado.options.parse_command_line()

    try:
        custom_settings = json.load(open(options.config, 'r'))
    except IOError:
        logger.warning(
            "Application started without configuration file.\n"
            "This is normal only during development and if you\n"
            "want to use MongoDB as data storage.\n"
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

    handlers = create_application_handlers()

    try:
        app = Application(handlers=handlers, **settings)
        server = tornado.httpserver.HTTPServer(app)
        server.listen(options.port)
    except Exception as e:
        return stop_running(str(e))

    # create references to application from SockJS handlers
    AdminSocketHandler.application = app
    Client.application = app

    app.initialize()

    # summarize run configuration writing it into logger
    logger.info("Application started")
    logger.info("Tornado port: {0}".format(options.port))
    if app.zmq_pub_sub_proxy:
        logger.info(
            "ZeroMQ XPUB: {0}, XSUB: {1}".format(
                app.zmq_xpub, app.zmq_xsub,
            )
        )
    else:
        logger.info(
            "ZeroMQ PUB - {0}; subscribed to {1}".format(
                app.zmq_pub_port, app.zmq_sub_address
            )
        )

    # finally, let's go
    try:
        ioloop_instance.start()
    except KeyboardInterrupt:
        logger.info('interrupted')
    finally:
        # clean
        if hasattr(app, 'pub_stream'):
            app.pub_stream.close()
        if hasattr(app, 'sub_stream'):
            app.sub_stream.stop_on_recv()
            app.sub_stream.close()


if __name__ == '__main__':
    main()
