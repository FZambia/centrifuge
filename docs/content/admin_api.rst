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

Centrifuge API url path is ``/api/ PROJECT_ID``, where PROJECT_ID must be replaced with your project ID
(you can see it in Centrifuge's web interface).

All you need to do is to send correctly constructed POST request to this endpoint. This request must have
two POST parameters: ``data`` and ``sign``. Data is a base64 encoded json string and sign is an hmac based on
project secret key, project ID and encoded data.

Data is originally a json object with two properties: ``method`` and ``params``.

``method`` is a name of action you want to do.

``params`` is an object with method arguments.

There are methods for managing project structure and
methods which allow to manage channels.


Methods for managing channels
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

These are **publish**, **unsubscribe**, **presence**, **history**.

Lets just go through each of methods and look what they do and which params you need
to provide.

**publish** - send message into channel of namespace. ``data`` is an actual information
you want to send into channel. **It must be valid JSON**.

.. code-block:: javascript

    {
        "method": "publish",
        "params": {
            "namespace": "NAMESPACE NAME",
            "channel": "CHANNEL NAME",
            "data": {}
        }
    }

**unsubscribe** - unsubscribe user with certain ID from channel.

.. code-block:: javascript

    {
        "method": "unsubscribe",
        "params": {
            "namespace": "NAMESPACE NAME",
            "channel": "CHANNEL NAME",
            "user": "USER ID"
    }

**presence** - get channel presence information (all clients currently subscribed on this channel).

.. code-block:: javascript

    {
        "method": "presence",
        "params": {
            "namespace": "NAMESPACE NAME",
            "channel": "CHANNEL NAME"
    }

**history** - get channel history information (list of last messages sent into channel).

.. code-block:: javascript

    {
        "method": "history",
        "params": {
            "namespace": "NAMESPACE NAME",
            "channel": "CHANNEL NAME"
    }


Now let's see on API which allow you to change project structure.

Methods for managing structure
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

There are lots of them. But in most cases you won't need them as Centrifuge has web
interface which helps with managing structure task.

**project_get** - get information about project options

**project_edit** - edit project options

**project_delete** - completely delete project

**regenerate_secret_key** - regenerate secret key for project (be careful with this)

**namespace_list** - get all project namespaces.

**namespace_get** - get namespace by its ``_id``

**namespace_edit** - edit namespace by its ``_id``

**namespace_delete** - delete namespace by its ``_id``


Methods above available for project administrators using project secret key.

But Centrifuge has another level of permissions which allows to run every
command above and also these:

**project_list** - get all projects

**project_create** - create new project

**dump_structure** - get all current structure.


You can access these methods using ``_`` (by default) for Project ID and
``api_secret`` from configuration file instead of project secret key (see
``[superuser]`` section in ``Cent`` description below). But using
this kind of API you need to provide project ID where necessary including
``_project`` (by default) key into params (which value is a project ID).



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

    [superuser]
    address = http://localhost:8000/api
    project_id = _
    secret_key = secret_key_from_configuration_file
    timeout = 5

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
