# -*- coding: utf-8 -*-
from __future__ import print_function
import time
import json
import logging

import tornado.ioloop
import tornado.web
from tornado.options import options, define
from cent.core import generate_token, authenticate


logging.getLogger().setLevel(logging.DEBUG)


define(
    "port", default=3000, help="app port", type=int
)
define(
    "centrifuge", default='localhost:8000',
    help="centrifuge address without url scheme", type=str
)
define(
    "project_id", default='', help="project id", type=str
)
define(
    "secret_key", default='', help="project secret key", type=str
)


# let it be your application's user ID
USER_ID = '2694'

INFO = json.dumps(None)

# uncomment this to send some additional default info
#INFO = json.dumps({
#    'first_name': 'Alexandr',
#    'last_name': 'Emelin'
#})


class IndexHandler(tornado.web.RequestHandler):

    def get(self):
        self.render('index.html')


def get_auth_data():

    user = USER_ID
    now = str(int(time.time()))
    token = generate_token(options.secret_key, options.project_id, user, now, user_info=INFO)

    auth_data = {
        'token': token,
        'user': user,
        'project': options.project_id,
        'timestamp': now,
        'info': INFO
    }

    return auth_data


class SockjsHandler(tornado.web.RequestHandler):

    def get(self):
        """
        Render template with data required to connect to Centrifuge using SockJS.
        """
        self.render(
            "index_sockjs.html",
            auth_data=get_auth_data(),
            centrifuge_address=options.centrifuge
        )


class WebsocketHandler(tornado.web.RequestHandler):

    def get(self):
        """
        Render template with data required to connect to Centrifuge using Websockets.
        """
        self.render(
            "index_websocket.html",
            auth_data=get_auth_data(),
            centrifuge_address=options.centrifuge
        )


class CheckHandler(tornado.web.RequestHandler):
    """
    Allow all users to subscribe on channels they want.
    """
    def check_xsrf_cookie(self):
        pass

    def post(self):

        # the list of users connected to Centrifuge with expired connection
        # web application must find deactivated users in this list
        users_to_check = json.loads(self.get_argument("users"))
        logging.info(users_to_check)

        # list of deactivated users
        deactivated_users = []

        # send list of deactivated users as json
        self.write(json.dumps(deactivated_users))


class AuthorizeHandler(tornado.web.RequestHandler):
    """
    Allow all users to subscribe on channels they want.
    """
    def check_xsrf_cookie(self):
        pass

    def post(self):

        user = self.get_argument("user")
        channel = self.get_argument("channel")

        logging.info("{0} wants to subscribe on {1} channel".format(user, channel))

        # web application now has user and channel and must decide that
        # user has permissions to subscribe on that channel
        # if permission denied - then you can return non 200 HTTP response

        # but here we allow to join any private channel and return additional
        # JSON info specific for channel
        self.write(json.dumps({
            'channel_data_example': 'you can add additional JSON data when authorizing'
        }))


class CentrifugeAuthHandler(tornado.web.RequestHandler):
    """
    Allow all users to subscribe on channels they want.
    """
    def check_xsrf_cookie(self):
        pass

    def post(self):

        client_id = self.get_argument("client_id")
        channels = self.get_arguments("channels")

        logging.info("{0} wants to subscribe on {1}".format(client_id, ", ".join(channels)))

        to_return = {}

        for channel in channels:
            info = json.dumps({
                'channel_data_example': 'you can add additional JSON data when authorizing'
            })
            to_return[channel] = {
                "status": 200,
                "auth": authenticate(options.secret_key, client_id, channel, info=info),
                "info": info
            }

        # but here we allow to join any private channel and return additional
        # JSON info specific for channel
        self.set_header('Content-Type', 'application/json; charset="utf-8"')
        self.write(json.dumps(to_return))


def run():
    options.parse_command_line()
    app = tornado.web.Application(
        [
            (r'/', IndexHandler),
            (r'/sockjs', SockjsHandler),
            (r'/ws', WebsocketHandler),
            (r'/check', CheckHandler),
            (r'/authorize', AuthorizeHandler),
            (r'/centrifuge/auth', CentrifugeAuthHandler)
        ],
        debug=True
    )
    app.listen(options.port)
    logging.info("app started, visit http://localhost:%s" % options.port)
    tornado.ioloop.IOLoop.instance().start()


def main():
    try:
        run()
    except KeyboardInterrupt:
        pass


if __name__ == '__main__':
    main()
