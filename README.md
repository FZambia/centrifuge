CENTRIFUGE
==========

Light and simple open-source platform for real-time message broadcasting in
your web applications.

This is something like [Pusher](http://pusher.com/) service - not so
powerful yet, but open-source and easy to setup.

It is built on top of [Tornado](http://www.tornadoweb.org/en/stable/) -
extremely fast and mature Python's async web server.

Centrifuge also uses [ZeroMQ](http://www.zeromq.org/) sockets for internal
communication and publish/subscribe operations.

To connect to Centrifuge from browser pure [Websockets](http://en.wikipedia.org/wiki/WebSocket)
or [SockJS](https://github.com/sockjs/sockjs-client) library can be
used. Socket.io support in future plans.

Centrifuge comes with administrative web interface and by default requires
[MongoDB](http://www.mongodb.org/) to keep information about users, projects, categories etc.

Please, read the [documentation](https://centrifuge.readthedocs.org/en/latest/) and look
at examples for more information.
