CENTRIFUGE
==========

Simple real-time messaging in web applications.

The main goal of Centrifuge is the same as of [Pusher](http://pusher.com/) or
[Pubnub](http://www.pubnub.com/) services. The main difference is that Centrifuge is
open-source and requires installation. Centrifuge is most similar to
[Faye](http://faye.jcoglan.com/)

Centrifuge is built on top of [Tornado](http://www.tornadoweb.org/en/stable/) -
extremely fast and mature Python's async web server.

Centrifuge uses [ZeroMQ](http://www.zeromq.org/) steroid sockets for internal
communication and publish/subscribe operations. There is an also support
for [Redis](http://redis.io/) PUB/SUB, so you can use it instead of ZeroMQ.

To connect to Centrifuge from browser pure [Websockets](http://en.wikipedia.org/wiki/WebSocket)
or [SockJS](https://github.com/sockjs/sockjs-client) library can be
used.

Centrifuge comes with administrative web interface to manage project/namespace
structure and monitor important messages.

Persistent data (projects, namespaces) by default stored in [SQLite](http://www.sqlite.org/) database.
But when running Centrifuge instance processes on different machines you should use [MongoDB](http://www.mongodb.org/)
or [PostgreSQL](http://www.postgresql.org/) backends instead of SQLite.

Please,

* read the [documentation](https://centrifuge.readthedocs.org/en/latest/)
* watch [screencast](http://www.youtube.com/watch?v=RCLnCexzfOk) - rather outdated but with pleasant background music.
* look at [examples](https://github.com/FZambia/centrifuge/tree/master/examples).


Main features
-------------

* Asynchronous backend on top of Tornado
* SockJS and pure Websockets endpoints
* Simple javascript client
* Presence and history data for channels
* Web interface for managing your projects
* Flexible channel settings through namespaces


Basic usage from browser
------------------------

```javascript
var centrifuge = new Centrifuge({
    url: 'http://localhost:8000/connection',  // Centrifuge SockJS connection endpoint
    token: 'TOKEN', // token based on project's secret key, project ID and user ID
    project: 'PROJECT_ID', // project ID from Centrifuge admin interface
    user: 'USER_ID' // your application user ID (can be empty for anonymous access)
});

centrifuge.on('connect', function() {

    console.log('connected');

    var subscription = centrifuge.subscribe('django', function(message) {
        // message from channel received
        console.log(message);
    });

    subscription.on('ready', function(){
        subscription.presence(function(message) {
            // information about who connected to channel at moment received
        });
        subscription.history(function(message) {
            // information about last messages sent into channel received
        });
        subscription.on('join', function(message) {
            // someone connected to channel
        });
        subscription.on('leave', function(message) {
            // someone disconnected from channel
        });
    });

});

centrifuge.on('disconnect', function(){
    console.log('disconnected');
});

centrifuge.connect();
```

For more information about javascript client API see [documentation chapter](https://centrifuge.readthedocs.org/en/latest/content/client_api.html)

Architecture diagram
--------------------

![centrifuge](https://raw.github.com/FZambia/centrifuge/master/docs/content/img/centrifuge_architecture.png "centrifuge")

Admin web interface
-------------------

![admin_web_interface](https://raw.github.com/FZambia/centrifuge/master/docs/content/img/main.png "admin web interface")


To run tests type the following from `tests` directory (`centrifuge` must be in PYTHONPATH):

```python
# IMPORTANT! Tests clear Redis database on every running. Be aware of this.
python -m unittest discover -p 'test_*.py'
```

Contributing
------------

Pull requests are welcome! But, please, follow next principles:

* keep things as simple as possible
* pep8
* python 2.6, 2.7 and 3.3 compatible

P.S. If BSD license of Centrifuge does not allow you to use it, tell me and I'll consider to change license.


[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/FZambia/centrifuge/trend.png)](https://bitdeli.com/free "Bitdeli Badge")

