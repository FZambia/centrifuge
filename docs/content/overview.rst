Overview
========

.. _overview:

Centrifuge is a simple server for real-time messaging in web applications.

In a few words: clients (users of your web application/site) connect to Centrifuge from browser,
after connecting clients subscribe on channels. Every message which was published into that
channel will be delivered to all clients which are currently subscribed on that channel.

To connect to Centrifuge from browser pure `Websockets <http://en.wikipedia.org/wiki/WebSocket>`_
or `SockJS <https://github.com/sockjs/sockjs-client>`_) library can be used. So it works in both
modern and old browsers (IE 7 supported). Centrifuge has `javascript client <https://github.com/FZambia/centrifuge/tree/master/javascript>`_ with simple API.

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
to write all these settings in JSON file and go without any dependency on database.


.. image:: img/main.png
    :width: 650 px


Centrifuge can be useful everywhere you need real-time web page updates.

There are tons of use cases - chats, graphs, comments, counters, games or when you just want to know
how many users currently watching web page and who they are.

Centrifuge can be easily integrated with your existing web site - you don't need to change your project
infrastructure and philosophy to get real-time events. Just install Centrifuge and let your users connect
to it.

There are tons of examples in internet about how to add real-time events on your site. But very few
of them provide complete, scalable, full-featured, ready to deploy solution. Centrifuge aims to be
such a solution with simplicity in mind.
