Description
===========

.. _description:

Overview
~~~~~~~~

Here I'll try to explain how Centrifuge actually works.

In a few words - clients from browsers connect to Centrifuge, after connecting clients
subscribe on channels. And every message which was published into channel will be sent
to all clients which are currently subscribed on this channel.

When you start Centrifuge instance you start Tornado instance on a certain port number.
That port number can be configured using command-line option ``--port`` . By default it is 8000.

In general you should provide path to JSON configuration file when starting Centrifuge instance
using ``--config`` option. You can start Centrifuge without configuration file but this is
not secure and must be used only during development. Configuration file must contain valid JSON.
But for now let's omit configuration file. By default Centrifuge will use insecure cookie secret,
no administrative password, local SQLite storage as structure database and no Memory engine (more
about what is structure and what is engine later).

So the final command to start one instance of Centrifuge will be

.. code-block:: bash

    centrifuge --config=config.json

Or just

.. code-block:: bash

    centrifuge

You can run more instances of Centrifuge using Redis engine. But for now one instance is more
than enough.

Well, you started one instance of Centrifuge - clients from web browsers can start connecting
to it.

There are two endpoints for connections - ``/connection`` for SockJS and
``/connection/websocket`` for pure Websocket connections. On browser side you now know the
url to connect - for our simple case it is ``http://localhost:8000/connection`` in case of
using SockJS library and ``ws://localhost:8000/connection/websocket`` in case of using
pure Websockets.

To communicate with Centrifuge from browser you should use javascript client which comes
with Centrifuge (find it in repository) and provides simple API. Please, read a chapter about
client API to get more information.

Sometimes you need to run more instances of Centrifuge and load balance clients between them.
As was mentioned above when you start default instance of Centrifuge - you start it with
Memory Engine. Centrifuge holds all state in memory. But to run several Centrifuge instances
we must have a way to share current state between instances. For this purpose Centrifuge
utilizes Redis. To run Centrifuge using Redis you should configure Redis Engine in configuration
file instead of default Memory Engine. See chapter about configuration file to see how you can
configure engine to use.

I suppose you properly created configuration file and  configured Redis Engine. Now you can start
several instances of Centrifuge. Let's start 2 instances. Open terminal and run first instance:

.. code-block:: bash

    centrifuge --config=config.json --port=8000

Then open another terminal window and run second instance using another tornado port:

.. code-block:: bash

    centrifuge --config=config.json --port=8001

Now two instances running and connected via Redis. Cool!

But what is an url to connect from browser - ``http://localhost:8000/connection`` or
``http://localhost:8001/connection``?

None of them, because Centrifuge must be kept behind proper load balancer such as Nginx.
Nginx must be configured in a way to balance client connections from browser between our
two instances. You can find Nginx configuration example in repo.

New client can connect to any of running instances. If client sends message we must
send that message to other clients including those who connected to another instance
at this moment. This is why we need Redis PUB/SUB here. All instances listen to special
Redis channels and receive messages from those channels.

Finally let's talk about structure database.

In Centrifuge you can create projects and namespaces in projects. This information
must be stored somewhere and shared between all running instances. To achieve this
SQLite or MongoDB or PostgreSQL can be used. If all your instances running on the
same machine any of them can be used. But if you deploy Centrifuge on several machines
it is impossible to use SQLite database. To avoid making query to database on every
request all structure information loaded into memory and then updated when something
in structure changed and periodically to avoid inconsistency. There is also an option
to set all structure in configuration file and go without any database.


Projects
~~~~~~~~

When you have running Centrifuge's instance and want to create web application using it -
first you should do is to add your project into Centrifuge. It's very simple - just fill
the form.

**name** - unique project name, must be written using ascii symbols only. This is project
slug, human-readable identity.

**display name** - project's name in web interface.

**auth address** - url for authorization purposes, when your web application's client
joins to Centrifuge - you can provide user id. Also you must provide permissions for
every connected user. More about user id and permissions later. Anyway this is an address
of your web application that will be used to authorize new client's connection. Centrifuge
sends POST request with user id and permissions to this url and your application must decide
to allow authorization or not.

**max auth attempts** - amount of attempts Centrifuge will try to validate user's permissions
sending POST request to ``auth address``

**back off interval** - at the moment when Centrifuge restarts your web application can
have lots of active connected clients. All those client will reconnect and Centrifuge will
send authorization request to your web application's ``auth address``. For such cases Centrifuge
has `exponential back-off <http://en.wikipedia.org/wiki/Exponential_backoff>`_ support to reduce
load on your application. This is time of back of minimum interval in milliseconds.

**back off max timeout** - maximum time in milliseconds for backoff timeout (time before client
connects to Centrifuge and sending authorization request to ``auth address``).

Channels
~~~~~~~~

Namespaces
~~~~~~~~~~

Centrifuge allows to configure channel's settings using namespaces.

You can create new namespace, configure its settings and after that every
channel which belongs to this namespace will have these settings. It's flexible and
provides a great control over channel behaviour.
