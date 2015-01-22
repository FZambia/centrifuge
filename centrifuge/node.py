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


engine = os.environ.get('CENTRIFUGE_ENGINE')
if not engine or engine == 'memory':
    engine_class_path = 'centrifuge.engine.memory.Engine'
elif engine == "redis":
    engine_class_path = 'centrifuge.engine.redis.Engine'
else:
    engine_class_path = engine

engine_class = namedAny(engine_class_path)


storage = os.environ.get('CENTRIFUGE_STORAGE')
if not storage or storage == 'sqlite':
    storage_class_path = 'centrifuge.structure.sqlite.Storage'
elif storage == "file":
    storage_class_path = 'centrifuge.structure.file.Storage'
else:
    storage_class_path = storage

storage_class = namedAny(storage_class_path)


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

from centrifuge.web.handlers import MainHandler
from centrifuge.web.handlers import AuthHandler
from centrifuge.web.handlers import LogoutHandler
from centrifuge.web.handlers import AdminSocketHandler
from centrifuge.web.handlers import Http404Handler
from centrifuge.web.handlers import ProjectCreateHandler
from centrifuge.web.handlers import NamespaceFormHandler
from centrifuge.web.handlers import ProjectDetailHandler
from centrifuge.web.handlers import StructureDumpHandler
from centrifuge.web.handlers import StructureLoadHandler


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
            r'/project/([^/]+)/([^/]+)$',
            ProjectDetailHandler,
            name="project_detail"
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
        ),
        tornado.web.url(
            r'/loads$', StructureLoadHandler, name="load_structure"
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

    try:
        custom_settings = json.load(open(options.config, 'r'))
    except IOError:
        logger.warning(
            "No configuration file found. "
            "In production make sure security settings provided"
        )
        custom_settings = {}

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
    if not sockjs_settings or not sockjs_settings.get("sockjs_url"):
        # SockJS CDN will be retired
        # see https://github.com/sockjs/sockjs-client/issues/198
        # if no explicit SockJS url provided in configuration file
        # then we use jsdelivr CDN instead of default cdn.sockjs.org
        # this can be fixed directly in SockJS-Tornado soon
        sockjs_settings["sockjs_url"] = "https://cdn.jsdelivr.net/sockjs/0.3/sockjs.min.js"

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

    logger.info("Storage class: {0}".format(storage_class_path))
    app.storage = storage_class(options)

    # create references to application from SockJS handlers
    AdminSocketHandler.application = app
    Client.application = app

    app.initialize()

    max_channel_length = custom_settings.get('max_channel_length')
    if max_channel_length:
        app.MAX_CHANNEL_LENGTH = max_channel_length

    admin_api_message_limit = custom_settings.get('admin_api_message_limit')
    if admin_api_message_limit:
        app.ADMIN_API_MESSAGE_LIMIT = admin_api_message_limit

    client_api_message_limit = custom_settings.get('client_api_message_limit')
    if client_api_message_limit:
        app.CLIENT_API_MESSAGE_LIMIT = client_api_message_limit

    owner_api_project_id = custom_settings.get('owner_api_project_id')
    if owner_api_project_id:
        app.OWNER_API_PROJECT_ID = owner_api_project_id

    owner_api_project_param = custom_settings.get('owner_api_project_param')
    if owner_api_project_param:
        app.OWNER_API_PROJECT_PARAM = owner_api_project_param

    connection_expire_check = custom_settings.get('connection_expire_check', True)
    if connection_expire_check:
        app.CONNECTION_EXPIRE_CHECK = connection_expire_check

    connection_expire_collect_interval = custom_settings.get('connection_expire_collect_interval')
    if connection_expire_collect_interval:
        app.CONNECTION_EXPIRE_COLLECT_INTERVAL = connection_expire_collect_interval

    connection_expire_check_interval = custom_settings.get('connection_expire_check_interval')
    if connection_expire_check_interval:
        app.CONNECTION_EXPIRE_CHECK_INTERVAL = connection_expire_check_interval

    logger.info("Tornado port: {0}, address: {1}".format(options.port, options.address))

    # finally, let's go
    try:
        ioloop_instance.start()
    except KeyboardInterrupt:
        logger.info('interrupted')
    finally:
        # cleaning
        if hasattr(app.engine, 'clean'):
            app.engine.clean()


if __name__ == '__main__':
    main()
