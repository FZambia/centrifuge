# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
import zmq
from zmq.eventloop import ioloop
from zmq.eventloop.zmqstream import ZMQStream


# Install ZMQ ioloop instead of a tornado ioloop
# http://zeromq.github.com/pyzmq/eventloop.html
ioloop.install()


import tornado
import tornado.web
import tornado.ioloop
import tornado.httpserver
from tornado.options import define, options

from .log import logger

import os
import sys
import json


define(
    "rep", default='tcp://*:6002', help="ZeroMQ REP socket address", type=str
)


define(
    "xsub", default="tcp://*:6000", help="ZeroMQ XPUB socket address", type=str
)


define(
    "xpub", default='tcp://*:6001', help="ZeroMQ XPUB socket address", type=str
)


def stop_running(msg):
    """
    Called only during initialization when critical error occurred.
    """
    logger.error(msg)
    sys.exit(1)


def main():

    options.parse_command_line()

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
        options=custom_settings
    )

    try:
        app = tornado.web.Application(settings)
        server = tornado.httpserver.HTTPServer(app)
        server.listen(options.port)
    except Exception as e:
        return stop_running(str(e))

    ctx = zmq.Context.instance()

    replier = ctx.socket(zmq.REP)
    replier.bind(options.rep)
    app.reply_stream = ZMQStream(replier)

    subscriber = ctx.socket(zmq.XSUB)
    subscriber.bind(options.xsub)
    # wrap xsub socket into ZeroMQ stream
    app.xsub_stream = ZMQStream(subscriber)

    publisher = ctx.socket(zmq.XPUB)
    publisher.bind(options.xpub)
    # wrap xpub socket into ZeroMQ stream
    app.xpub_stream = ZMQStream(publisher)

    try:
        ioloop_instance.start()
    except KeyboardInterrupt:
        pass
    finally:
        del replier, subscriber, publisher
        ctx.term()

    # zmq.proxy(publisher, subscriber, None)


if __name__ == '__main__':
    main()
