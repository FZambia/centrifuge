Admin API
=========

.. _admin_api:

Overview
~~~~~~~~

When clients publish into channel - your application does not know about those messages.
In most cases you need to receive event from client, process it, probably validate and save
into database and then broadcast to other connected clients. In this case you must not
use channels which namespace allows publishing. The common pattern in this situation is
receive new message via AJAX, do whatever you need with it and then publish into Centrifuge
using HTTP API. If your backend written on Python you can use Cent API client. If you use
other language don't worry - I will describe how to communicate with Centrifuge API endpoint
right now.

Centrifuge API url path is ``/api/ PROJECT_ID``. All you need to do is to send correctly
constructed POST request to this endpoint. This request must have two POST parameters:
``data`` and ``sign``. Data is a base64 encoded json string and sign is an hmac based on
project secret key, project ID and encoded data.

Data is originally a json object with two properties:
method and params. Method is the name of action you want to do. It can be publish,
unsubscribe, presence, history. Params is an object with method arguments.

Lets just go through each of methods and look what they do and which params you need
to provide.

publish - send message into channel of namespace.

.. code-block:: javascript

    {
        "method": "publish",
        "params": {
            "namespace": "NAMESPACE NAME",
            "channel": "CHANNEL NAME",
            "data": "hello"
        }
    }

unsubscribe - unsubscribe user from channel.

.. code-block:: javascript

    {
        "method": "unsubscribe",
        "params": {
            "namespace": "NAMESPACE NAME",
            "channel": "CHANNEL NAME",
            "user": "USER ID"
    }

presence - get channel presence information.

.. code-block:: javascript

    {
        "method": "presence",
        "params": {
            "namespace": "NAMESPACE NAME",
            "channel": "CHANNEL NAME"
    }

history - get channel history information.

.. code-block:: javascript

    {
        "method": "history",
        "params": {
            "namespace": "NAMESPACE NAME",
            "channel": "CHANNEL NAME"
    }

That's all for API commands. Now you know the way to control your channels.


Cent
~~~~

Cent is a way to communicate with Centrifuge from python code or
from console(terminal).


To install:

.. code-block:: bash

    pip install cent


By default Cent uses `.centrc` configuration file from your home directory.

Here is an example of config file's content:

.. code-block:: bash

    [python]
    address = http://localhost:8000/api
    project_id = 51b229f778b83c2eced3a76b
    secret_key = 994021f2dc354d7893d88b90d430498e
    timeout = 5


Project ID and Secret Key can be found on project's settings page in administrator's web interface.


The most obvious case of using Cent is broadcasting events into channels.

It is easy enough:

.. code-block:: bash

    cent python publish --params='{"namespace": "django", "channel": "news", "data": {"title": "Django 1.6 finally released", "text": "Release keynotes:..."}}'


- *cent* is the name of program
- *python* is the name of section in configuration file
- *publish* is the method name you want to call
- *--params* is a JSON string with method parameters, in this case of broadcast you should provide namespace, channel and data parameters.


If request was successful you'll get something like this in response:

.. code-block:: bash

    {'error': None, 'body': True, 'uid': None, 'method': 'publish'}


In case of any error you will get its description.


Cent contains Client class to send messages to Centrifuge from your python-powered backend:

.. code-block:: python

    from cent.core import Client

    client = Client("http://localhost:8000/api", "project_id", "project_secret_key")
    result, error = client.send(
        "publish", {
            "namespace": "python",
            "channel": "django",
            "data": "hello world"
        }
    )


Python
~~~~~~

If your backend Python powered and you don't want to install Cent, you can just copy
``Client`` class from Cent source code (``cent.core.Client``) and use it as was shown
above.
