Private channels
================

.. _private_channels:

So Centrifuge 0.7.0 introduced new private channel subscription mechanism. All channels
starting with ``$`` (by default) considered private. In chapter about javascript client
you have seen that subscribing on private channel from javascript client does not differ
from subscribing on usual channels. But you should implement an endpoint in your web
application that will check if current users can subscribe on certain private channels.

By default javascript client will sen AJAX POST request to ``/centrifuge/auth`` url. You
can change this address and add additional request headers via js client initialization
options (``authEndpoint`` and ``authHeaders``).

POST request includes two parameters: ``client`` and ``channels``. Client is a string with
current client ID and channels is one or more channels current user wants to subscribe to.

I think it's simplier to explain on example.

Lets imagine that client wants to subscribe on two private channels: ``$one`` and ``$two``.

Here is a javascript code to subscribe on them:

.. code-block:: javascript

    centrifuge.subscribe('$one', function(message) {
        // process message
    });

    centrifuge.subscribe('$two', function(message) {
        // process message
    });


In this case Centrifuge will send two separate POST requests to your web app. There is an
option to batch this requests into one using ``startAuthBatching`` and ``stopAuthBatching``
methods. Like this:

.. code-block:: javascript

    centrifuge.startAuthBatching();

    centrifuge.subscribe('$one', function(message) {
        // process message
    });

    centrifuge.subscribe('$two', function(message) {
        // process message
    });

    centrifuge.stopAuthBatching();

In this case one POST request with 2 channels in ``channels`` parameter will be send.
Let's look at simplified example for Tornado how to implement auth endpoint:

.. code-block:: python

    from cent.core import generate_channel_sign

    class CentrifugeAuthHandler(tornado.web.RequestHandler):

        def check_xsrf_cookie(self):
            pass

        def post(self):

            client_id = self.get_argument("client")
            channels = self.get_arguments("channels")
            logging.info("{0} wants to subscribe on {1}".format(client_id, ", ".join(channels)))

            to_return = {}

            for channel in channels:
                info = json.dumps({
                    'channel_extra_info_example': 'you can add additional JSON data when authorizing'
                })
                sign = generate_channel_sign(
                    options.secret_key, client_id, channel, info=info
                )
                to_return[channel] = {
                    "sign": sign,
                    "info": info
                }

            # but here we allow to join any private channel and return additional
            # JSON info specific for channel
            self.set_header('Content-Type', 'application/json; charset="utf-8"')
            self.write(json.dumps(to_return))

In this example we allow user to subscribe on any private channel. If you want to
reject subscription - then you can add "status" key and set it to something not
equal to 200, for example 403:

.. code-block:: python

    from cent.core import generate_channel_sign

    class CentrifugeAuthHandler(tornado.web.RequestHandler):

        def check_xsrf_cookie(self):
            pass

        def post(self):

            client_id = self.get_argument("client")
            channels = self.get_arguments("channels")
            logging.info("{0} wants to subscribe on {1}".format(client_id, ", ".join(channels)))

            to_return = {}

            for channel in channels:
                sign = generate_channel_sign(
                    options.secret_key, client_id, channel
                )
                to_return[channel] = {
                    "status": 403,
                }

            # but here we allow to join any private channel and return additional
            # JSON info specific for channel
            self.set_header('Content-Type', 'application/json; charset="utf-8"')
            self.write(json.dumps(to_return))

If user deactivated in your application then you can just return 403 Forbidden response:

.. code-block:: python

    from cent.core import generate_channel_sign

    class CentrifugeAuthHandler(tornado.web.RequestHandler):

        def check_xsrf_cookie(self):
            pass

        def post(self):
            raise tornado.web.HTTPError(403)


This will prevent client from subscribing to any private channel.