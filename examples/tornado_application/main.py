# -*- coding: utf-8 -*-
from __future__ import print_function
import hmac
import time
import json
import logging

import six
import tornado.ioloop
import tornado.web
from tornado.options import options, define


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


def get_client_token(secret_key, project_id, user, timestamp, info=None):
    """
    Create token to validate information provided by new connection.
    """
    sign = hmac.new(six.b(str(secret_key)))
    sign.update(six.b(project_id))
    sign.update(six.b(user))
    sign.update(six.b(timestamp))
    if info is not None:
        sign.update(six.b(info))
    token = sign.hexdigest()
    return token


class IndexHandler(tornado.web.RequestHandler):

    def get(self):
        self.render('index.html')


def get_auth_data():

    user = USER_ID
    now = str(int(time.time()))
    token = get_client_token(
        options.secret_key, options.project_id, user, now, info=INFO
    )

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


def run():
    options.parse_command_line()
    app = tornado.web.Application(
        [
            (r'/', IndexHandler),
            (r'/sockjs', SockjsHandler),
            (r'/ws', WebsocketHandler),
            (r'/check', CheckHandler),
            (r'/authorize', AuthorizeHandler),
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
