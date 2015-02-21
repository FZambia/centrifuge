CENTRIFUGE
==========

Simple real-time messaging in web applications. [Demo instance on Heroku](https://centrifuge-demo.herokuapp.com) - password `demo`.

Quick start
-----------
```bash
pip install centrifuge
centrifuge
```

Go to [http://localhost:8000](http://localhost:8000) - this is an administrative interface of Centrifuge node you just started. More about installation and configuration in [documentation](https://centrifuge.readthedocs.org/en/latest/).

Alternatively you can quickly install Centrifuge on Heroku (administrative password will be `password`):

[![Deploy](https://www.herokucdn.com/deploy/button.png)](https://heroku.com/deploy?template=https://github.com/centrifugal/heroku-centrifuge)

You can also run Centrifuge in a Docker container by running:
```bash
docker build -t centrifuge
docker run -it -p 8000:8000 centrifuge
```

If you want to contribute into Centrifuge - some steps below to help you configure development environment:
```
mkdir centrifuge
cd centrifuge
virtualenv env
. env/bin/activate
git clone https://github.com/centrifugal/centrifuge.git src/
cd src
pip install -r requirements.txt
export PYTHONPATH=.
python centrifuge/node.py
```

Overview
--------

In a few words: clients (users of your web application/site) connect to Centrifuge from browser,
after connecting clients subscribe on channels. Every message which was published into that
channel will be delivered to all clients which are currently subscribed on that channel.

To connect to Centrifuge from browser pure [Websockets](http://en.wikipedia.org/wiki/WebSocket)
or [SockJS](https://github.com/sockjs/sockjs-client) library can be used. So it works in both
modern and old browsers (IE 7 supported). Centrifuge has [javascript client](https://github.com/centrifugal/centrifuge-js/) with simple API.

Backend is built on top of [Tornado](http://www.tornadoweb.org/en/stable/) - fast and mature
asynchronous web server which can handle thousands of simultaneous connections.

Centrifuge scales using [Redis](http://redis.io/) PUB/SUB capabilities.
Single full-featured instance of Centrifuge run by default without extra dependency
on Redis.

Centrifuge comes with administrative web interface to manage project/namespace
structure and monitor important messages in real-time.

Persistent data (projects, namespaces) by default stored in [SQLite](http://www.sqlite.org/) database.
When running Centrifuge instance processes on different machines [MongoDB](https://github.com/centrifugal/centrifuge-mongodb)
or [PostgreSQL](https://github.com/centrifugal/centrifuge-postgresql) backends can be used instead of SQLite. There is an option
to hard-code all these settings in JSON file and go without any dependency on database.

There are tons of examples in internet about how to add real-time events on your site. But very few
of them provide complete, scalable, full-featured, ready to deploy solution. Centrifuge aims to be
such a solution with simplicity in mind.


Main features
-------------

* Asynchronous backend on top of Tornado
* SockJS and pure Websockets connection endpoints
* Simple javascript client
* Presence information, message history, join/leave events for channels
* Web interface to manage your projects
* Flexible channel settings via namespaces
* Language agnostic - you can go with Centrifuge even if your site built in Perl, PHP, Ruby etc.
* Easily integrates with existing web site.

To get more information:

* read the [documentation](https://centrifuge.readthedocs.org/en/latest/)
* look at [examples](https://github.com/centrifugal/centrifuge/tree/master/examples).

Various packages and tools related to Centrifuge located in [Centrifugal](https://github.com/centrifugal)
organization here on Github.

![scheme](https://raw.github.com/centrifugal/centrifuge/master/docs/content/img/centrifuge.png "scheme")

Similar projects / alternatives:

* [Pusher](http://pusher.com/) (cloud service)
* [Pubnub](http://www.pubnub.com/) (cloud service)
* [Faye](http://faye.jcoglan.com/)


Basic usage from browser
------------------------

```javascript
var centrifuge = new Centrifuge({
    url: 'http://localhost:8000/connection',  // Centrifuge SockJS connection endpoint
    project: 'PROJECT_ID', // project ID from Centrifuge admin interface
    user: 'USER_ID', // your application user ID (can be empty for anonymous access)
    timestamp: '1395086390', // current UNIX timestamp (number of seconds as string)
    token: 'TOKEN', // HMAC token based on project's secret key, project ID, user ID and timestamp
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

Admin web interface
-------------------

![admin_web_interface](https://raw.github.com/centrifugal/centrifuge/master/docs/content/img/centrifuge.gif "admin web interface")


Tests
-----

IMPORTANT! At moment tests require Redis running and clear database on every running. Be aware of this!

```bash
make test
```

Contributing
------------

Pull requests are welcome! But, please, follow next principles:

* keep things simple
* pep8 friendly
* python 2.6, 2.7, 3.3 and 3.4 compatible

LICENSE
-------

MIT

[![Requirements Status](https://requires.io/github/centrifugal/centrifuge/requirements.png?branch=master)](https://requires.io/github/centrifugal/centrifuge/requirements/?branch=master)
