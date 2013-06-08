Getting started
===============

.. _cent_starting:


Cent is a way to communicate with Centrifuge from python code or
from console(terminal).


Installation
~~~~~~~~~~~~

.. code-block:: bash

    pip install cent


Configuration
~~~~~~~~~~~~~

By default Cent uses `.centrc` configuration file from your home directory.

Here is an example of config file's content:

.. code-block:: bash

    [python]
    address = http://localhost:8000/rpc
    project_id = 51b229f778b83c2eced3a76b
    secret_key = 994021f2dc354d7893d88b90d430498e
    timeout = 5


Project ID and Secret Key can be found on project's settings page in administrator's web interface.


Using
~~~~~

The most obvious case of using Cent is broadcasting events into channels.

It is easy enough:

.. code-block:: bash

    cent python broadcast --params='{"category": "django", "channel": "news", "data": {"title": "Django 1.6 finally released", "text": "Release keynotes:..."}}'

