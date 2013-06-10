Centrifuge's configuration file
===============================

.. _configuration_file:


Example
~~~~~~~

Here is minimal configuration file required:

.. code-block:: bash

    {
        "password": "admin",
        "cookie_secret": "secret",
        "storage": {
            "module": "centrifuge.storage.mongodb",
            "settings": {
                "host": "localhost",
                "port": 27017,
                "name": "centrifuge",
                "pool_size": 10
            }
        }
    }


With PostgreSQL this file look like:

.. code-block:: bash

    {
        "password": "admin",
        "cookie_secret": "secret",
        "storage": {
            "module": "centrifuge.storage.postgresql",
            "settings": {
                "host": "localhost",
                "port": 27017,
                "name": "centrifuge",
                "password": "",
                "user": "postgres",
                "pool_size": 10
            }
        }
    }



Description
~~~~~~~~~~~

- **cookie_secret** - used for security purposes, fill it with long random string and keep it in secret

- **password** - administrator's password. Can be omitted during development.

- **storage** - section with database backend settings. No alternatives except default MongoDB for this moment.
