# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import os
import sys
import json
import logging
import tornado
import tornado.web
import tornado.ioloop
import tornado.options
import tornado.httpserver
from tornado.options import define, options

from centrifuge.log import logger
from centrifuge.utils import namedAny


define(
    "debug", default=False, help="tornado debug mode", type=bool
)

define(
    "port", default=8000, help="app port", type=int
)

define(
    "address", default="", help="address to bind to", type=str
)

define(
    "config", default='config.json', help="JSON config file", type=str
)

define(
    "name", default='', help="unique node name", type=str
)

define(
    "web", default='', help="path to web app directory", type=str
)

engine = os.environ.get('CENTRIFUGE_ENGINE')
if not engine or engine == 'memory':
    engine_class_path = 'centrifuge.engine.memory.Engine'
elif engine == "redis":
    engine_class_path = 'centrifuge.engine.redis.Engine'
else:
    engine_class_path = engine

engine_class = namedAny(engine_class_path)


tornado.options.parse_command_line()


def setup_logging_level(level):
    """
    Set logging level for Centrifuge logger according to command-line option provided
    """
    if level == 'none':
        return

    logger.setLevel(getattr(logging, level.upper()))


setup_logging_level(options.logging)


from sockjs.tornado import SockJSRouter

from centrifuge.core import Application
from centrifuge.handlers import ApiHandler
from centrifuge.handlers import SockjsConnection
from centrifuge.handlers import Client

from centrifuge.web.handlers import InfoHandler
from centrifuge.web.handlers import AuthHandler
from centrifuge.web.handlers import AdminWebSocketHandler
from centrifuge.web.handlers import ActionHandler


def stop_running(msg):
    """
    Called only during initialization when critical error occurred.
    """
    logger.error(msg)
    sys.exit(1)


def create_application_handlers(sockjs_settings):

    handlers = [
        tornado.web.url(r'/api/([^/]+)/?$', ApiHandler, name="api"),
        tornado.web.url(r'/info/$', InfoHandler, name="info"),
        tornado.web.url(r'/action/$', ActionHandler, name="action"),
        tornado.web.url(r'/auth/$', AuthHandler, name="auth"),
        (r'/socket', AdminWebSocketHandler),
    ]

    if options.web:
        logger.info("serving web application from {0}".format(os.path.abspath(options.web)))
        handlers.append(
            (
                r'/(.*)',
                tornado.web.StaticFileHandler,
                {"path": options.web, "default_filename": "index.html"}
            )
        )

    # create SockJS route for client connections
    client_sock_router = SockJSRouter(
        SockjsConnection, '/connection', user_settings=sockjs_settings
    )
    handlers = client_sock_router.urls + handlers

    return handlers


def create_centrifuge_application():

    try:
        custom_settings = json.load(open(options.config, 'r'))
    except IOError:
        return stop_running("No configuration file found.")

    # override security related options using environment variable
    # value if exists
    for option_name in ["password", "cookie_secret", "api_secret"]:
        environment_var_name = "CENTRIFUGE_{0}".format(option_name.upper())
        environment_value = os.environ.get(environment_var_name)
        if environment_value:
            logger.debug("using {0} environment variable for {1} option value".format(
                environment_var_name, option_name
            ))
            custom_settings[option_name] = environment_value

    if os.environ.get("CENTRIFUGE_INSECURE") == "1":
        custom_settings["insecure"] = True

    settings = dict(
        cookie_secret=custom_settings.get("cookie_secret", "bad secret"),
        template_path=os.path.join(
            os.path.dirname(__file__),
            os.path.join("web/frontend", "templates")
        ),
        xsrf_cookies=False,
        autoescape="xhtml_escape",
        debug=options.debug,
        options=options,
        config=custom_settings
    )

    sockjs_settings = custom_settings.get("sockjs_settings", {})
    if not sockjs_settings or not sockjs_settings.get("sockjs_url"):
        # SockJS CDN will be retired
        # see https://github.com/sockjs/sockjs-client/issues/198
        # if no explicit SockJS url provided in configuration file
        # then we use jsdelivr CDN instead of default cdn.sockjs.org
        # this can be fixed directly in SockJS-Tornado soon
        sockjs_settings["sockjs_url"] = "https://cdn.jsdelivr.net/sockjs/1.0/sockjs.min.js"

    handlers = create_application_handlers(sockjs_settings)

    # custom settings to configure the tornado HTTPServer
    tornado_settings = custom_settings.get("tornado_settings", {})
    logger.debug("tornado_settings: %s", tornado_settings)
    if 'io_loop' in tornado_settings:
        stop_running(
            "The io_loop in tornado_settings is not supported for now."
            )

    try:
        app = Application(handlers=handlers, **settings)
        server = tornado.httpserver.HTTPServer(app, **tornado_settings)
        server.listen(options.port, address=options.address)
    except Exception as e:
        return stop_running(str(e))

    logger.info("Engine class: {0}".format(engine_class_path))
    app.engine = engine_class(app)

    # create reference to application from Client
    Client.application = app

    app.initialize()

    logger.info("Tornado port: {0}, address: {1}".format(options.port, options.address))
    return app


def main():
    ioloop_instance = tornado.ioloop.IOLoop.instance()
    create_centrifuge_application()
    try:
        ioloop_instance.start()
    except KeyboardInterrupt:
        logger.info('interrupted')


if __name__ == '__main__':
    main()
