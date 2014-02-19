How it works
============

.. _description:

Here I'll try to explain how Centrifuge actually works.

In a few words
~~~~~~~~~~~~~~

Clients from browsers connect to Centrifuge, after connecting clients subscribe
on channels. And every message which was published into channel will be sent
to all clients which are currently subscribed on this channel.


In detail
~~~~~~~~~

This is an architecture diagram of Centrifuge:

.. image:: img/centrifuge_architecture.png
    :width: 650 px


When you start Centrifuge instance you start Tornado instance on a certain port number.
That port number can be configured using command-line option ``--port`` . By default it is 8000.

In general you should provide path to JSON configuration file when starting Centrifuge instance
using ``--config`` option. You can start Centrifuge without configuration file but this is
not secure and must be used only during development.

Configuration file must contain valid JSON. But for now let's omit configuration file.
By default Centrifuge will use insecure cookie secret, no administrative password, local SQLite
storage as structure database and no Redis (no presence and message history data will be available).

In production you always need to provide proper configuration file with secure settings!

So the final command to start one instance of Centrifuge will be

.. code-block:: bash

    centrifuge --config=config.json

You can run more instances to scale but in this case you should use one of available
PUB/SUB backends - Redis or ZeroMQ based.

Well, you started one instance of Centrifuge - clients from web browsers can start connecting to it.

There are two endpoints for browser connections - ``/connection`` for SockJS and
``/connection/websocket`` for pure Websocket connections. On browser side you now know the
url to connect - for our simple case it is ``http://localhost:port/connection`` in case of
using SockJS library and ``ws://localhost:port/connection/websocket`` in case of using
pure Websockets.

To communicate with Centrifuge from browser you should use javascript client which comes
with Centrifuge (find it in repository) and provides simple API. Please, read a chapter about
client API to get more information.

Ok, now you have one working instance. But sometimes it is not enough and you need to run
more instances of Centrifuge and load balance clients between them.

As was mentioned above it's time to use one of available PUB/SUB backends.

Lets see on Redis backend first and then on ZeroMQ.

Redis is very simple and recommended way to scale Centrifuge. I suppose that you have it installed
and running with default settings.

Start first Centrifuge instance:

.. code-block:: bash

    centrifuge --config=config.json --redis


See th difference? Yep, we added ``--redis`` option. This tells Centrifuge to connect to Redis
and use its PUB/SUB capabilities.

But our goal is to run several instances of Centrifuge. So lets run another one:

.. code-block:: bash

    centrifuge --config=config.json --redis --port==8001


Note, that in this case we used ``--port`` option. This is necessary because every Centrifuge
instance must be run on its own port number.

So two instances running and connected via Redis. Cool!

But what is an url to connect from browser - ``http://localhost:8000/connection`` or
``http://localhost:8001/connection``? None of them, because Centrifuge must be kept
behind proper load balancer such as Nginx. Nginx must be configured in a way to balance
client connections from browser between our two instances. You can find Nginx configuration
example in repo.

New client can connect to any of running instances. If client sends message we must
send that message to other clients including those who connected to another instance
at this moment. This is why we need PUB/SUB here. All instances listen to special Redis
channels and get messages from those channels.

My final note will be that you have other Redis related command-line options:

.. code-block:: bash

    centrifuge --config=config.json --redis --redis_host=localhost --redis_port=6379 --redis_password=

As you can see those options are Redis address, port and password.


Now lets talk about using ZeroMQ backend for PUB/SUB. It's a bit harder than going with Redis
so I suppose you are experienced enough and understand why you need ZeroMQ instead of Redis.

There are two ways of configuring ZeroMQ with Centrifuge.

First way - manually set instance's publish socket and all publish sockets current
instance must subscribe to. You should use these options for it. The drawback is that you
should support correct settings for all instances and restart all instances with new
socket configuration options when adding new instance.

.. code-block:: bash

    centrifuge --port=8000 --zmq_pub_port=7000 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001
    centrifuge --port=8001 --zmq_pub_port=7001 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001

Look, we selected two different ports for ZeroMQ PUB socket using ``--zmq_pub_port``
option. And we told every instance a comma-separated list of all PUB socket addresses
using ``--zmq_sub_address`` option. Instances now connected and you can load balance
clients between them.

Another way - use XPUB/XSUB proxy. Things will work according to this scheme.

.. image:: img/xpub_xsub.png
    :width: 650 px


In this case you only need to provide proxy endpoints in command-line options which will
be the same for all Centrifuge instances. Also you must run the proxy itself. The drawback
is that proxy is a single point of failure. There is proxy written in Go language. You
can run it instead of python version coming with Centrifuge.


.. code-block:: bash

    centrifuge --zmq_pub_sub_proxy --zmq_xsub=tcp://localhost:6000 --zmq_xpub=tcp://localhost:6001


We told Centrifuge to use XPUB/XSUB proxy using flag ``--zmq_pub_sub_proxy`` and set
XSUB (``--zmq_xsub``) and XPUB (``--zmq_xpub``) endpoints.

And to start proxy:

.. code-block:: bash

    xpub_xsub --xsub=tcp://*:6000 --xpub=tcp://*:6001


Now instances connected through XPUB/XSUB proxy. Success!


Our next step will be talking about how presence and history data for channels work.

Centrifuge can use process memory (single node only) or Redis (one or more nodes) for this.
State settings must be set up in configuration file.


Finally let's talk about structure database.

In Centrifuge you can create projects and namespaces in projects. This information
must be stored somewhere and shared between all running instances. To achieve this
SQLite or MongoDB or PostgreSQL can be used. If all your instances running on the
same machine any of them can be used. But if you deploy Centrifuge on several machines
it is impossible to use SQLite database. To avoid making query to database on every
request all structure information loaded into memory and then updated when something
in structure changed and periodically to avoid inconsistency. There is also an option
to set all structure in configuration file and go without any database.

