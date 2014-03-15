CENTRIFUGE
==========

Simple real-time messaging in web applications.

In a few words: clients (users of your web application/site) connect to Centrifuge from browser,
after connecting clients subscribe on channels. Every message which was published into that
channel will be delivered to all clients which are currently subscribed on that channel.

To connect to Centrifuge from browser pure [Websockets](http://en.wikipedia.org/wiki/WebSocket)
or [SockJS](https://github.com/sockjs/sockjs-client) library can be used. So it works in both
modern and old browsers (IE 7 supported). Centrifuge has javascript client with simple API.

Backend is built on top of [Tornado](http://www.tornadoweb.org/en/stable/) - fast and mature
asynchronous web server which can handle thousands of simultaneous connections.

Centrifuge scales using [Redis](http://redis.io/) PUB/SUB capabilities.
Single full-featured instance of Centrifuge run by default without extra dependency
on Redis.

Centrifuge comes with administrative web interface to manage project/namespace
structure and monitor important messages in real-time.

Persistent data (projects, namespaces) by default stored in [SQLite](http://www.sqlite.org/) database.
When running Centrifuge instance processes on different machines [MongoDB](http://www.mongodb.org/)
or [PostgreSQL](http://www.postgresql.org/) backends can be used instead of SQLite. There is an option
to hard-code all these settings in configuration file and go without any dependency on database.


Main features
-------------

* Asynchronous backend on top of Tornado
* SockJS and pure Websockets connection endpoints
* Simple javascript client
* Presence information, message history, join/leave events for channels
* Web interface to manage your projects
* Flexible channel settings via namespaces
* Language agnostic - you can go with Centrifuge even if your site built in Perl, PHP, Ruby etc.


To get more information:

* read the [documentation](https://centrifuge.readthedocs.org/en/latest/)
* look at [examples](https://github.com/FZambia/centrifuge/tree/master/examples).

Various packages and tools related to Centrifuge located in Centrifugal
organization on Github: https://github.com/centrifugal

Similar projects / alternatives:

* [Pusher](http://pusher.com/) (cloud service)
* [Pubnub](http://www.pubnub.com/) (cloud service)
* [Faye](http://faye.jcoglan.com/)


Basic usage from browser
------------------------

```javascript
var centrifuge = new Centrifuge({
    url: 'http://localhost:8000/connection',  // Centrifuge SockJS connection endpoint
    token: 'TOKEN', // token based on project's secret key, project ID, user ID and timestamp
    project: 'PROJECT_ID', // project ID from Centrifuge admin interface
    user: 'USER_ID', // your application user ID (can be empty for anonymous access)
    timestamp: '123454545' // current UNIX timestamp (number of seconds as string)
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

LICENSE
-------

MIT

[![Bitdeli Badge](https://d2weczhvl823v0.cloudfront.net/FZambia/centrifuge/trend.png)](https://bitdeli.com/free "Bitdeli Badge")
[![Requirements Status](https://requires.io/github/FZambia/centrifuge/requirements.png?branch=master)](https://requires.io/github/FZambia/centrifuge/requirements/?branch=master)

