Overview
========

.. _overview:

What is it
----------

Centrifuge is a simple server for real-time messaging in web applications.

This is something like `Pusher <http://pusher.com/>`_ or `Pubnub <http://pubnub.com/>`_ services -
not so powerful yet, but open-source, self hosted and easy to setup. The closest analogue is
`Faye <https://github.com/faye/faye>`_.

It is built on top of `Tornado <http://www.tornadoweb.org/en/stable/>`_ -
extremely fast and mature Python's async web server.

Centrifuge uses `ZeroMQ <http://www.zeromq.org/>`_ steroid sockets for internal
communication and publish/subscribe operations.

For presence and history data Centrifuge utilizes `Redis <http://redis.io/>`_ - advanced and super fast
in memory key-value store.

To connect to Centrifuge from browser pure `Websockets <http://en.wikipedia.org/wiki/WebSocket>`_
or [SockJS](https://github.com/sockjs/sockjs-client) library can be
used.

Centrifuge comes with administrative web interface to manage project/namespace structure and monitor important
messages.

Persistent data (projects, namespaces) by default stored in `SQLite <http://www.sqlite.org/>`_ database.
But when running Centrifuge instance processes on different machines you should use `MongoDB <http://www.mongodb.org/>`_
or `PostgreSQL <http://www.postgresql.org/>`_ backends instead of SQLite for structure management.


.. image:: img/main.png
    :width: 650 px


Where it can be useful
----------------------

Everywhere you need real-time web page updates.

There are tons of use cases where Centrifuge could be helpful - chat, graphs,
comments, counters, games etc.

Or you just want to know how many users currently watching web page and who they are.