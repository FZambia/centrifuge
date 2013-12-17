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
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge.structure.sqlite",
            "settings": {
                "path": "centrifuge.db"
            }
        },
        "state": null
    }


With MongoDB as structure storage:

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge.structure.mongodb",
            "settings": {
                "host": "localhost",
                "port": 27017,
                "name": "centrifuge",
                "pool_size": 10
            }
        },
        state: null
    }


With PostgreSQL this file look like:

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge.structure.postgresql",
            "settings": {
                "host": "localhost",
                "port": 27017,
                "name": "centrifuge",
                "password": "",
                "user": "postgres",
                "pool_size": 10
            }
        },
        "state": null
    }
**In case of using single instance of Centrifuge** you can enable presence and history
support without any dependencies. All data will be stored in memory of process. In
this case when you restart process - you lose all information about presence and history.
Here is a configuration with in-process-memory state enabled:

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge.structure.sqlite",
            "settings": {
                "path": "centrifuge.db"
            }
        },
        "state": {
            "storage": "centrifuge.state.base.State",
            "settings": {}
        }
    }




But when you use several instances of Centrifuge - Redis required for presence and history data.
Lets configure Centrifuge to use Redis as state storage:

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "module": "centrifuge.structure.sqlite",
            "settings": {
                "path": "centrifuge.db"
            }
        },
        "state": {
            "storage": "centrifuge.state.redis.State",
            "settings": {
                "host": "localhost",
                "port": 6379
            }
        }
    }


Description:

- **password** - administrator's web interface password.

- **cookie_secret** - used for security purposes, fill it with long random string and keep it in secret.

- **api_secret** - administrator's API secret key.

- **structure** - section with database settings in which persistent information will be stored.

- **state** - settings to enable history and presence data for channels.

There is also a possibility to override default SockJS-Tornado settings using Centrifuge
configuration file. Example:

.. code-block::javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge.structure.sqlite",
            "settings": {
                "path": "/tmp/centrifuge.db"
            }
        },
        "state": null,
        "sockjs_settings": {
            "sockjs_url": "https://centrifuge.example.com/static/libs/sockjs/sockjs-0.3.4.min.js"
        }
    }

Here I set custom ``sockjs_url`` option, list of all available options can be found in sockjs-tornado source code: `show on Github <https://github.com/mrjoes/sockjs-tornado/blob/master/sockjs/tornado/router.py#L14>`_


Command-line options
~~~~~~~~~~~~~~~~~~~~

Centrifuge has some command line arguments.

ZeroMQ is a default PUB/SUB mechanism in Centrifuge.

To create 2 connected instances of Centrifuge with ZeroMQ PUB/SUB you can use can do:


.. code-block:: bash

    centrifuge --port=8000 --zmq_pub_port=7000 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001
    centrifuge --port=8001 --zmq_pub_port=7001 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001


With correct Nginx configuration you can load balance clients from browsers between them.


To run Centrifuge in debug Tornado's mode:

.. code-block:: bash

    centrifuge --debug

Note, that because of PyZMQ bug Tornado's autoreloading feature will not work when using
ZeroMQ PUB/SUB. Until new release of PyZMQ where this error was fixed.


To run Centrifuge with ZeroMQ XPUB/XSUB proxy:

.. code-block:: bash

    centrifuge --zmq_pub_sub_proxy --zmq_xsub=tcp://localhost:6000 --zmq_xpub=tcp://localhost:6001


But in case of using XPUB/XSUB proxy you should actually start this proxy:

.. code-block:: bash

    xpub_xsub --xsub=tcp://*:6000 --xpub=tcp://*:6001


Using XPUB/XSUB proxy is nice because you don't need to restart all your Centrifuge processes
when you add new one, but it's a single point of failure. Remember about it.

There is also XPUB/XSUB proxy implemented in Go lang: `gist on Github <https://gist.github.com/FZambia/5955032>`_


To run Centrifuge with Redis PUB/SUB:

.. code-block:: bash

    centrifuge --config=config.json --redis --redis_host=localhost --redis_port=6379


If you know that single instance is enough for you - you can use Base PUB/SUB
which does not require ZeroMQ or Redis:

.. code-block:: bash

    centrifuge --config=config.json --base
