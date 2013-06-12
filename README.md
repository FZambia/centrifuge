CENTRIFUGE
==========

Light and simple open-source platform for real-time message broadcasting in
your web applications.

The main goal of Centrifuge is the same as in [Pusher](http://pusher.com/) or
[Pubnub](http://www.pubnub.com/) services. The main difference is that Centrifuge is
open-source and requires installation (it is worth noting that installation is rather simple).

It is built on top of [Tornado](http://www.tornadoweb.org/en/stable/) -
extremely fast and mature Python's async web server.

Centrifuge also uses [ZeroMQ](http://www.zeromq.org/) sockets for internal
communication and publish/subscribe operations.

To connect to Centrifuge from browser pure [Websockets](http://en.wikipedia.org/wiki/WebSocket)
or [SockJS](https://github.com/sockjs/sockjs-client) library can be
used.

Centrifuge comes with administrative web interface and by default requires
[MongoDB](http://www.mongodb.org/) to keep information about projects, categories etc.
You can also use [PostgreSQL](http://www.postgresql.org/) instead of MongoDB.

Please, read the [documentation](https://centrifuge.readthedocs.org/en/latest/) and look
at [examples](https://github.com/FZambia/centrifuge/tree/master/examples) for more information.

![admin_web_interface](https://raw.github.com/FZambia/centrifuge/master/docs/starting/main.png "admin web interface")

![centrifuge](https://raw.github.com/FZambia/centrifuge/master/docs/description/centrifuge_architecture.png "centrifuge")
