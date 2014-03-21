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
no administrative password, local SQLite storage as structure database and Memory engine (more
about what is structure and what is engine later).

So the final command to start one instance of Centrifuge will be

.. code-block:: bash

    centrifuge --config=config.json

Or just

.. code-block:: bash

    centrifuge

You can run more instances of Centrifuge using Redis engine. But for most cases one instance is more
than enough.

Well, you started one instance of Centrifuge - clients from web browsers can start connecting
to it.

There are two endpoints for connections - ``/connection`` for SockJS and
``/connection/websocket`` for pure Websocket connections. On browser side you now know the
url to connect - for our simple case it is ``http://localhost:8000/connection`` in case of
using SockJS library and ``ws://localhost:8000/connection/websocket`` in case of using
pure Websockets.

To communicate with Centrifuge from browser you should use javascript client which comes
with Centrifuge (find it `in repository <https://github.com/FZambia/centrifuge/tree/master/javascript>`_) and provides simple API. Please, read a chapter about
client API to get more information.

Sometimes you need to run more instances of Centrifuge and load balance clients between them.
As was mentioned above when you start default instance of Centrifuge - you start it with
Memory Engine. Centrifuge holds all state in memory. But to run several Centrifuge instances
we must have a way to share current state between instances. For this purpose Centrifuge
utilizes Redis. To run Centrifuge using Redis you should run centrifuge with Redis Engine
instead of default Memory Engine.

First, install and run Redis.

Now you can start several instances of Centrifuge. Let's start 2 instances.

Open terminal and run first instance:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --port=8000

I.e. you tell Centrifuge to use Redis Engine providing environment variable
``CENTRIGUGE_ENGINE`` when launching it.

Explore available command line options specific for Redis engine using ``--help``:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --help

``CENTRIFUGE_ENGINE`` can be ``memory``, ``redis`` or pythonic path to custom engine
like ``path.to.custom.Engine``

Then open another terminal window and run second instance using another tornado port:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --port=8001

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


In Centrifuge you can create projects and namespaces in projects. This information
must be stored somewhere and shared between all running instances. To achieve this by
default Centrifuge uses SQLite database. If all your instances running on the
same machine - it's OK. But if you deploy Centrifuge on several machines
it is impossible to use SQLite database. In this case you can use `PostgreSQL backend <https://github.com/centrifugal/centrifuge-postgresql>`_ or
`MongoDB backend <https://github.com/centrifugal/centrifuge-mongodb>`_. You can also use
PostgeSQL or MongoDB backends if your web site already uses them.

To avoid making query to database on every request all structure information loaded into memory and then updated when something
in structure changed and periodically to avoid inconsistency. There is also an option
to set all structure in configuration file and go without any database (no database, no
dependencies - but structure can not be changed via API or web interface).

You can choose structure backend in the same way as engine - via environment variable
``CENTRIFUGE_STORAGE``:

.. code-block:: bash

    CENTRIFUGE_STORAGE=sqlite centrifuge --path=/tmp/centrifuge.db

Use default SQLite database.

Or:

.. code-block:: bash

    CENTRIFUGE_STORAGE=file centrifuge --port=8001 --path=/path/to/json/file/with/structure

Use structure from JSON file.

Or:

.. code-block:: bash

    CENTRIFUGE_STORAGE=centrifuge_mongodb.Storage centrifuge --mongodb_host=localhost

To use installed MongoDB backend.

Or:

.. code-block:: bash

    CENTRIFUGE_STORAGE=centrifuge_postgresql.Storage centrifuge

As in case of engine you can use ``--help`` to see available options for each of
structure storage backends.


Projects
~~~~~~~~

When you have running Centrifuge's instance and want to create web application using it -
first you should do is to add your project into Centrifuge. It's very simple - just fill
the form.

**project name** - unique project name, must be written using ascii letters, numbers, underscores or hyphens.

**display name** - project's name in web interface.

**connection check** - turn on connection check mechanism. When clients connect to Centrifuge
they provide timestamp - the UNIX time when their token was created. Every connection in project has
connection lifetime (see below). If connection check turned on - Centrifuge will periodically search
for expired connections and ask your web application which of expired clients must be dropped.
This mechanism is disabled by default because it needs extra endpoint to be written in your
application (at ``connection check url address`` - see below).

One more time: every connection has a time of expiration which is configurable via project settings.
Centrifuge periodically searches for expired connections and sends POST request to your web app with
list of user IDs whose connections expired. Your web app must filter this list  and return a list of
deactivated users - Centrifuge immediately disconnects them. There is a possibility though that client
will try to reconnect with his credentials right after he was disconnected. If his credentials already
expired - his connection will be paused until next check request. If his credentials are not expired
- connection will be accepted by Centrifuge. But when connection expire your web application will
tell Centrifuge that this user is deactivated - so connection will be dropped forever. As you can see
there is a little compromise in security model which you should be aware of - deactivated user can
theoretically listen to channels until his connection expire. The time of connection expiration is
configurable (see below).

**connection lifetime in seconds** - this is a time interval in seconds for connection to expire.
Keep it as large as possible in your case.

**connection check url address** - Centrifuge will send a list of users whose connections expired to
this address (POST request).

**minimum connection check interval** - you can configure minimum interval between connection check POST requests to
``connection check url address`` (in seconds)

**max auth attempts** - amount of attempts Centrifuge will try to validate user's permissions
sending POST request to ``auth address``

**back off interval** - at the moment when Centrifuge restarts your web application can
have lots of active connected clients. All those client will reconnect and Centrifuge will
send authorization request to your web application's ``auth address``. For such cases Centrifuge
has `exponential back-off <http://en.wikipedia.org/wiki/Exponential_backoff>`_ support to reduce
load on your application. This is time of back of minimum interval in milliseconds.

**back off max timeout** - maximum time in milliseconds for backoff timeout (time before client
connects to Centrifuge and sending authorization request to ``auth address``).

**is watching** - publish messages into admin channel (messages will be visible in web interface).
Turn it off if you expect high load in channels.

**is private** - authorize every subscription on channel using POST request to provided auth address (see below)

**auth url address** - url for authorization purposes, when your web application's client
joins to Centrifuge - you can provide user id. Also you must provide permissions for
every connected user. More about user id and permissions later. Anyway this is an address
of your web application that will be used to authorize new client's connection. Centrifuge
sends POST request with user id and permissions to this url and your application must decide
to allow authorization or not.

**publish** - allow clients to publish messages in channels (your web application never receive those messages)

**presence** - enable/disable presence information

**history** - enable/disable history of messages

**join/leave messages** - enable/disable sending join(leave) messages when client subscribes
on channel (unsubscribes from channel)

Channels
~~~~~~~~

The central part of Centrifuge is channels. Channels is a route for messages. Clients subscribe on
channels, messages are being published into channels, channels everywhere.

Channel is just a string - `news`, `comments`, `red fox` are valid channel names.

BUT! You should remember several things.

First, channel name length is limited by 255 characters by default (can be changed via configuration file option ``max_channel_length``)

Second, ``:`` and ``#`` symbols has a special role in channel names!

``:`` - is a separator for namespace (see what is namespace below).

So if channel name is ``public:chat`` - then Centrifuge will search for namespace ``public``.

``#`` is a separator to create private channels for users without sending POST request to
your web application. For example if channel is ``news#user42`` then only user with id ``user42``
cab subscribe on this channel.

Moreover you can provide several user IDs in channel name separated by comma: ``dialog#user42,user43`` -
in this case only ``user42`` and ``user43`` will be able to subscribe on this channel.


Namespaces
~~~~~~~~~~

Centrifuge allows to configure channel's settings using namespaces.

You can create new namespace, configure its settings and after that every
channel which belongs to this namespace will have these settings. It's flexible and
provides a great control over channel behaviour. You can reduce the amount of messages
travelling around dramatically by configuring namespace (for example disable join/leave)
messages if you don't need them.

Namespace has several parameters - they are the same as project's settings. But with extra
one:

**namespace name** - unique namespace name: must consist of letters, numbers, underscores or hyphens

As was mentioned above if you want to attach channel to namespace - you must include namespace
name into channel name with ``:`` as separator:

For example:

``public:news``

``private:news``

Where ``public`` and ``private`` are namespace names.
