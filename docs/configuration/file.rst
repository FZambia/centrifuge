Centrifuge's configuration file
===============================

.. _configuration_file:


Example
~~~~~~~

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


Description
~~~~~~~~~~~

- **password** - administrator's password. Can be omitted during development.

- **cookie_secret** - used for security purposes, fill it with long random string and keep it in secret

- **structure** - section with database settings in which persistent information will be stored.

- **state** - Redis settings to enable history and presence data for channels.
