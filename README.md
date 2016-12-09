CENTRIFUGE
==========

**WARNING!!! Centrifuge server migrated to Go language - it's now called [Centrifugo](https://github.com/centrifugal/centrifugo) and lives in another repo. This repo is for history only!**

It's not compatible with entire Centrifugal stack so you have to use certain versions of libraries.

Here is a list of libraries versions compatible with Centrifuge:

* centrifuge-js [0.9.0](https://github.com/centrifugal/centrifuge-js/tree/0.9.0)
* cent [v0.6.0](https://github.com/centrifugal/cent/tree/v0.6.0)
* adjacent [v0.3.0](https://github.com/centrifugal/adjacent/tree/v0.3.0)
* web [v0.1.0](https://github.com/centrifugal/web/tree/v0.1.0)
* examples [v0.1.0](https://github.com/centrifugal/examples/tree/v0.1.0)
* phpcent [0.6.1](https://github.com/centrifugal/phpcent/tree/0.6.1)
* centrifuge-ruby [v0.1.0](https://github.com/centrifugal/centrifuge-ruby/tree/v0.1.0)

Please, see [new documentation](http://fzambia.gitbooks.io/centrifugal/content/) for the entire Centrifugal stack.


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

There are tons of examples in internet about how to add real-time events on your site. But very few
of them provide complete, scalable, full-featured, ready to deploy solution. Centrifuge aims to be
such a solution with simplicity in mind.


Main features
-------------

* Asynchronous backend on top of Tornado
* SockJS and pure Websockets connection endpoints
* Simple javascript client
* Presence information, message history, join/leave events for channels
* Admin web interface
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

Tests
-----

IMPORTANT! At moment tests require Redis running and clear database on every running. Be aware of this!

```bash
make test
```

LICENSE
-------

MIT

[![Requirements Status](https://requires.io/github/centrifugal/centrifuge/requirements.png?branch=master)](https://requires.io/github/centrifugal/centrifuge/requirements/?branch=master)
[![Build Status](https://travis-ci.org/centrifugal/centrifuge.svg?branch=master)](https://travis-ci.org/centrifugal/centrifuge)
