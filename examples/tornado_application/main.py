# -*- coding: utf-8 -*-
import tornado.ioloop
import tornado.web
from tornado.options import options, define
import logging
import hmac
import json


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


def get_client_token(secret_key, project_id, user, info=None):
    """
    Create token to validate information provided by new connection.
    """
    sign = hmac.new(str(secret_key))
    sign.update(project_id)
    sign.update(user)
    if info is not None:
        sign.update(info)
    token = sign.hexdigest()
    print token
    return token


class IndexHandler(tornado.web.RequestHandler):

    def get(self):
        self.render('index.html')


class SockjsHandler(tornado.web.RequestHandler):

    def get(self):
        """
        Render template with data required to authenticate connection
        in Centrifuge.
        """
        user = USER_ID

        token = get_client_token(
            options.secret_key, options.project_id, user, info=INFO
        )

        auth_data = {
            'token': token,
            'user': user,
            'project': options.project_id,
            'info': INFO
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
            options.secret_key, options.project_id, user, info=INFO
        )

        auth_data = {
            'token': token,
            'user': user,
            'project': options.project_id,
            'info': INFO
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
