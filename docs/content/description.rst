Description
===========

.. _description:

Overview
~~~~~~~~

In this chapter I'll try to explain how Centrifuge actually works.

In a few words - clients from browsers connect to Centrifuge, after connecting clients
subscribe on channels. And every message which was published into channel will be sent
to all clients which are currently subscribed on this channel.

When you start Centrifuge instance you start Tornado on a certain port number.
That port number can be configured using command-line option ``--port`` . By default ``8000``.
You can also specify the address to bind to with the ``--address`` option. For example you
can specify ``localhost`` which is recommended if you want to keep Centrifuge behind a
proxy (e.g.: Nginx). The port and the address will eventually be used by Tornado's TCPServer.

You should provide path to JSON configuration file when starting Centrifuge instance
using ``--config`` option. Configuration file must contain valid JSON.

So the final command to start one instance of Centrifuge will be

.. code-block:: bash

    centrifuge --config=config.json


You can scale and run more instances of Centrifuge on multiple machines using Redis engine.
But for most cases one instance is more than enough.

Well, when you started one instance of Centrifuge - clients from web browsers can start
connecting to it.

There are two endpoints for connections:
- ``/connection`` for SockJS connections
- ``/connection/websocket`` for pure Websocket connections

On browser side you now know the url to connect - for our simple case it is ``http://localhost:8000/connection``
in case of using SockJS library and ``ws://localhost:8000/connection/websocket`` in case of using
pure Websockets.

To communicate with Centrifuge from browser you should use javascript client which comes
with Centrifuge (find it `in its own repository <https://github.com/centrifugal/centrifuge-js>`_)
and provides simple API. Please, read a `chapter <https://centrifuge.readthedocs.org/en/latest/content/client_api.html>`_ about client API to get more information.

Sometimes you need to run more instances of Centrifuge and load balance clients between them.
As was mentioned above when you start default instance of Centrifuge - you start it with
Memory Engine. In this case Centrifuge holds all state in memory. But to run several Centrifuge
instances we must provide a way to share current state between instances. For this purpose Centrifuge
utilizes Redis. To run Centrifuge with Redis you should run Centrifuge with Redis Engine
instead of default Memory Engine.

First, install and run Redis (it's recommended to use Redis of version 2.6.9 or greater).

Now you can start several instances of Centrifuge. Let's start 2 instances.

Open terminal and run first instance:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --config=config.json --port=8000

I.e. you tell Centrifuge to use Redis Engine providing environment variable
``CENTRIGUGE_ENGINE`` when launching it.

Explore available command line options specific for Redis engine using ``--help``:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --help

``CENTRIFUGE_ENGINE`` can be ``memory``, ``redis`` or path to custom engine class
like ``path.to.custom.Engine``

Then open another terminal window and run second instance on another port:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --config=config.json --port=8001

Now two instances running and connected via Redis. Great!

But what is an url to connect from browser - ``http://localhost:8000/connection`` or
``http://localhost:8001/connection``?

None of them, because Centrifuge must be kept behind proper load balancer such as Nginx.
Nginx must be configured in a way to balance client connections from browser between our
two instances. You can find Nginx configuration example in documentation or repo.

New client can connect to any of running instances. If client sends message we must
send that message to other clients including those who connected to another instance
at this moment. This is why we need Redis PUB/SUB here. All instances listen to special
Redis channels and receive messages from those channels.


Projects
~~~~~~~~

When you have Centrifuge instance and want to create web application using it -
first you should do is to add your project into Centrifuge configuration file into
**structure** array. **structure** is generally an array of projects in Centrifuge.

.. code-block::javascript

    {
      "password": "password",
      "cookie_secret": "cookie_secret",
      "structure": [
        {
          "name": "development",
          "secret": "secret",
          "namespaces": [
            {
              "name": "public",
              "publish": true,
              "watch": true,
              "presence": true,
              "join_leave": true,
              "history_size": 10,
              "history_lifetime": 30
            }
          ]
        }
      ]
    }




**name** - unique project name, must be written using ascii letters, numbers, underscores or hyphens.

**secret** - project secret key, used to sign API requests, create client tokens. Only Centrifuge
and your web application backend must know the value of this secret. Make it unique and strong enough.

**connection_lifetime** - this is a time interval in seconds for connection to expire.
Keep it as large as possible in your case. When clients connect to Centrifuge
they provide timestamp - the UNIX time when their token was created. Every connection in
project has connection lifetime (see below). This mechanism is disabled by default
(connection_lifetime=0) and requires extra endpoint to be implemented in your application.

**watch** - publish messages into admin channel (messages will be visible in web interface).
Turn it off if you expect high load in channels.

**publish** - allow clients to publish messages in channels (your web application never receive those messages)

**anonymous** - allow anonymous (with empty USER ID) clients to subscribe on channels

**presence** - enable/disable presence information

**join_leave** - enable/disable sending join(leave) messages when client subscribes
on channel (unsubscribes from channel)

**history_size** - Centrifuge keeps all history in memory. In process memory in case of using Memory Engine
and in Redis (which also in-memory store) in case of using Redis Engine. So it's very important to limit
maximum amount of messages in channel history. This setting is exactly for this. By default history
size is 0 - this means that channels will have no history messages at all.

**history_lifetime** - as all history is storing in memory it is also very important to get rid of old history
data for unused (inactive for a long time) channels. This is interval in seconds to keep history for channel
after last publishing into it. If you leave this setting to 0 - history will never expire but it is not
recommended due to design of Centrifuge - as it will lead to memory leaks.


Channels
~~~~~~~~

The central part of Centrifuge is channels. Channel is a route for messages. Clients subscribe on
channels, messages are being published into channels, channels everywhere.

Channel is just a string - ``news``, ``comments`` are valid channel names.

BUT! You should remember several things.

First, channel name length is limited by 255 characters by default (can be changed via configuration file option ``max_channel_length``)

Second, ``:`` and ``#`` and ``$`` symbols has a special role in channel names!

``:`` - is a separator for namespace (see what is namespace below).

So if channel name is ``public:chat`` - then Centrifuge will search for namespace ``public``.

``#`` is a separator to create private channels for users without sending POST request to
your web application. For example if channel is ``news#user42`` then only user with id ``user42``
can subscribe on this channel.

Moreover you can provide several user IDs in channel name separated by comma: ``dialog#user42,user43`` -
in this case only ``user42`` and ``user43`` will be able to subscribe on this channel.

If channel starts with ``$`` (by default) then it's considered private. Read special
chapter in docs about private channel subscriptions.


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

**name** - unique namespace name: must consist of letters, numbers, underscores or hyphens

As was mentioned above if you want to attach channel to namespace - you must include namespace
name into channel name with ``:`` as separator:

For example:

``news:messages``

``gossips:messages``

Where ``news`` and ``gossips`` are namespace names.
