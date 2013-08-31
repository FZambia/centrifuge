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
        "structure": {
            "module": "centrifuge.structure.sqlite",
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
        "structure": {
            "module": "centrifuge.structure.mongodb",
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
        "structure": {
            "module": "centrifuge.structure.postgresql",
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

Channel presence and history require Redis. In examples above you can see "state"
option set to ``null``. To enable presence and history fill this option with Redis
settings:

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "structure": {
            "module": "centrifuge.structure.sqlite",
            "settings": {
                "path": "centrifuge.db"
            }
        },
        "state": {
            "host": "localhost",
            "port": 6379
        }
    }


Of course you should install and run Redis before running Centrifuge with it.


Description:

- **password** - administrator's password. Can be omitted during development.

- **cookie_secret** - used for security purposes, fill it with long random string and keep it in secret

- **structure** - section with database settings in which persistent information will be stored.

- **state** - Redis settings to enable history and presence data for channels.


Command-line options
~~~~~~~~~~~~~~~~~~~~

Centrifuge has some command line arguments.


Example. To create 2 connected instances of Centrifuge you can use something like this:


.. code-block:: bash

    centrifuge --port=8000 --zmq_pub_port=7000 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001
    centrifuge --port=8001 --zmq_pub_port=7001 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001


With correct Nginx configuration you can load balance clients from browsers between them.


To run Centrifuge in debug Tornado's mode:

.. code-block:: bash

    centrifuge --debug

Note, that because of PyZMQ bug Tornado's autoreloading feature will not work. Until new
release of PyZMQ where this error was fixed.


To run Centrifuge with XPUB/XSUB proxy:

.. code-block:: bash

    centrifuge --zmq_pub_sub_proxy --zmq_xsub=tcp://localhost:6000 --zmq_xpub=tcp://localhost:6001


But in case of using XPUB/XSUB proxy you should actually start this proxy:

.. code-block:: bash

    xpub_xsub --xsub=tcp://*:6000 --xpub=tcp://*:6001


Using XPUB/XSUB proxy is nice because you don't need to restart all your Centrifuge processes
when you add new one, but it's a single point of failure. Remember about it.

There is also XPUB/XSUB proxy implemented in Go lang: `gist on Github <https://gist.github.com/FZambia/5955032>`_