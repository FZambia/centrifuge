Configuration
=============

.. _configuration:


Configuration file
~~~~~~~~~~~~~~~~~~

Example

Here is minimal configuration file required:

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret"
    }


Description:

- **password** - administrator's web interface password.

- **cookie_secret** - used for security purposes, fill it with long random string and keep it in secret.

- **api_secret** - administrator's API secret key.

There is also a possibility to override default SockJS-Tornado settings using Centrifuge
configuration file. Example:

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "sockjs_settings": {
            "sockjs_url": "https://centrifuge.example.com/static/libs/sockjs/sockjs-0.3.4.min.js"
        }
    }


Here I set custom ``sockjs_url`` option, list of all available options can be found in sockjs-tornado source code: `show on Github <https://github.com/mrjoes/sockjs-tornado/blob/master/sockjs/tornado/router.py#L14>`_

Centrifuge also allows to collect and export various metrics into Graphite.
You can configure metric collecting and exporting behaviour using ``metrics``
object in configuration JSON.

In example below I enable logging metrics, and export into https://www.hostedgraphite.com/ service
providing prefix, host and port to send metrics via UDP.

..code-block::javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "metrics": {
            "admin": true,
            "log": true,
            "graphite": true,
            "graphite_host": "carbon.hostedgraphite.com",
            "graphite_port": 2003,
            "graphite_prefix": "MY_HOSTED_GRAPHITE_KEY.centrifuge",
            "interval": 10
        }
    }

Metrics will be aggregated in a 10 seconds interval and then will be sent into log, into
admin channel and into Graphite.

At moment Centrifuge collects for each node:

* broadcast - time in milliseconds spent to broadcast messages (average, min, max, count of broadcasts)
* connect - amount and rate of connect attempts to Centrifuge
* messages - amount and rate of messages published
* channels - amount of active channels
* clients - amount of connected clients
* unique_clients - amount of unique clients connected


Command-line options
~~~~~~~~~~~~~~~~~~~~

Centrifuge has several command line arguments.

``--config`` - path to configuration json file

``--debug`` - run Centrifuge in debug mode:

``--port`` - port to bind (default 8000)

``--name`` - unique node name (optional) - will be used in web interface metric table or in graphite data path


Some other command line options come with engine or structure storage backend -
explore them using ``--help``, for example:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --help






