# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
from tornado.options import options, define
import logging
import hmac


logging.getLogger().setLevel(logging.DEBUG)


define(
    "port", default=3000, help="app port", type=int
)
define(
    "centrifuge", default='localhost:8000',
    help="centrifuge address without url scheme", type=str
)
define(
    "public_key", default='', help="project public key", type=str
)
define(
    "secret_key", default='', help="project secret key", type=str
)


# let it be your application's user ID
USER_ID = '2694'


def get_client_token(secret_key, public_key, user):
    """
    Create token to validate information provided by new connection.
    """
    sign = hmac.new(str(secret_key))
    sign.update(user)
    sign.update(public_key)
    token = sign.hexdigest()
    return token


class SockjsHandler(tornado.web.RequestHandler):

    def get(self):
        """
        Render template with data required to authenticate connection
        in Centrifuge.
        """
        user = USER_ID

        token = get_client_token(
            options.secret_key, options.public_key, user
        )

        auth_data = {
            'token': token,
            'user': user,
            'public_key': options.public_key
        }

        self.render(
            "index_sockjs.html",
            auth_data=auth_data,
            centrifuge_address=options.centrifuge
        )


class WebsocketHandler(tornado.web.RequestHandler):

    def get(self):
        """
        Render template with data required to authenticate connection
        in Centrifuge.
        """
        user = USER_ID

        token = get_client_token(
            options.secret_key, options.public_key, user
        )

        auth_data = {
            'token': token,
            'user': user,
            'public_key': options.public_key
        }

        self.render(
            "index_websocket.html",
            auth_data=auth_data,
            centrifuge_address=options.centrifuge
        )


class ValidateHandler(tornado.web.RequestHandler):
    """
    Allow all users to subscribe on channels they want.
    """
    def check_xsrf_cookie(self):
        pass

    def post(self):
        self.write('ok')


def run():
    options.parse_command_line()
    app = tornado.web.Application(
        [
            (r'/', SockjsHandler),
            (r'/ws', WebsocketHandler),
            (r'/validate', ValidateHandler),
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
