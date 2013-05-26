Centrifuge's configuration file
===============================

.. _configuration file:


Example
~~~~~~~

Here is minimal configuration file required:

.. code-block:: bash

    {
        "debug": true,
        "cookie_secret": "secret",
        "storage": {
            "module": "centrifuge.storage.mongodb",
            "settings": {
                "host": "localhost",
                "port": 27017,
                "name": "centrifuge",
                "max_pool_size": 10
            }
        }
    }


Description
~~~~~~~~~~~

- **debug** - turn it to false in production environment and keep true while developing.

- **cookie_secret** - used for security purposes, fill it with long random string and keep it in secret

- **storage** - section with database backend settings. No alternatives except default MongoDB for this moment.
