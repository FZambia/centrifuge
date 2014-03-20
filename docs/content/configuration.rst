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


Command-line options
~~~~~~~~~~~~~~~~~~~~

Centrifuge has several command line arguments.

``--config`` - path to configuration json file

``--debug`` - run Centrifuge in debug mode:

``--port`` - port to bind (default 8000)


Some other command line options come with engine or structure storage backend -
explore them using ``--help``

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --help






