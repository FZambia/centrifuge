Overview
========

.. _overview:

What is it
----------

Centrifuge is a simple server for real-time messaging in web applications.

In a few words: clients (users of your web application/site) connect to Centrifuge from browser,
after connecting clients subscribe on channels. Every message which was published into that
channel will be delivered to all clients which are currently subscribed on that channel.

To connect to Centrifuge from browser pure `Websockets <http://en.wikipedia.org/wiki/WebSocket>`_
or `SockJS <https://github.com/sockjs/sockjs-client>`_) library can be used. So it works in both
modern and old browsers (IE 7 supported). Centrifuge has javascript client with simple API.

Backend is built on top of `Tornado <http://www.tornadoweb.org/en/stable/>`_ - fast and mature
asynchronous web server which can handle thousands of simultaneous connections.

Centrifuge scales using `Redis <http://redis.io/>`_ PUB/SUB capabilities.
Single full-featured instance of Centrifuge run by default without extra dependency
on Redis.

Centrifuge comes with administrative web interface to manage project/namespace
structure and monitor important messages in real-time.

Persistent data (projects, namespaces) by default stored in `SQLite <http://www.sqlite.org/>`_ database.
When running Centrifuge instance processes on different machines `MongoDB <http://www.mongodb.org/>`_
or `PostgreSQL <http://www.postgresql.org/>`_ backends can be used instead of SQLite. There is an option
to hard-code all these settings in configuration file and go without any dependency on database.


.. image:: img/main.png
    :width: 650 px


Where it can be useful
----------------------

Everywhere you need real-time web page updates. There are tons of use cases where Centrifuge
could be helpful - chat, graphs, comments, counters, games etc. Or if you just want to know
how many users currently watching web page and who they are.
