# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.


from tornado.options import define, options
import zmq


define(
    "xsub", default="tcp://*:6000", help="ZeroMQ XPUB socket address", type=str
)


define(
    "xpub", default='tcp://*:6001', help="ZeroMQ XPUB socket address", type=str
)


def main():

    options.parse_command_line()

    ctx = zmq.Context.instance()

    subscriber = ctx.socket(zmq.XSUB)
    subscriber.bind(options.xsub)

    publisher = ctx.socket(zmq.XPUB)
    publisher.bind(options.xpub)

    try:
        zmq.proxy(publisher, subscriber, None)
    except KeyboardInterrupt:
        pass
    finally:
        del subscriber, publisher
        ctx.term()


if __name__ == '__main__':
    main()
