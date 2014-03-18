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
            "storage": "centrifuge.structure.sqlite.Storage",
            "settings": {
                "path": "centrifuge.db"
            }
        },
        "engine": null
    }


With MongoDB as structure storage (``centrifuge-mongodb`` package must be installed):

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge_mongodb.Storage",
            "settings": {
                "host": "localhost",
                "port": 27017,
                "name": "centrifuge",
                "pool_size": 10
            }
        },
        "engine": null
    }


With PostgreSQL this file look like (``centrifuge-postgresql`` package must be installed):

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge_postgresql.Storage",
            "settings": {
                "host": "localhost",
                "port": 27017,
                "name": "centrifuge",
                "password": "",
                "user": "postgres",
                "pool_size": 10
            }
        },
        "engine": null
    }

You can also specify PostgreSQL connection params as database url or specify
an OS environment variable that holds value of the PostgreSQL connection url:

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge_postgresql.Storage",
            "settings": {
                "url": "postgres://user:pass@host:port/dbname"
            }
        },
        "engine": null
    }

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge_postgresql.Storage",
            "settings": {
                "url": "$DATABASE_URL"
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
            "storage": "centrifuge.structure.sqlite.Storage",
            "settings": {
                "path": "centrifuge.db"
            }
        },
        "engine": {
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
            "module": "centrifuge.structure.sqlite.Storage",
            "settings": {
                "path": "centrifuge.db"
            }
        },
        "engine": {
            "class": "centrifuge.engine.redis.Engine",
            "settings": {
                "host": "localhost",
                "port": 6379,
                "password": ""
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

.. code-block:: javascript

    {
        "password": "admin",
        "cookie_secret": "secret",
        "api_secret": "secret",
        "structure": {
            "storage": "centrifuge.structure.sqlite.Storage",
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

Centrifuge has several command line arguments.
