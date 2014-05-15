v0.5.2
======

* Centrifuge now collects various metrics and has an option to log them or to export them into Graphite
* New optional `--name` launch option to give your node human readable unique name (will be used in web interface and Graphite data path)
* History for inactive channels now expires to prevent permanent memory grows (expiration time is configurable via project/namespace settings).

At moment Centrifuge collects following metrics:

* broadcast - time in milliseconds spent to broadcast messages (average, min, max, count of broadcasts)
* connect - amount and rate of connect attempts to Centrifuge
* messages - amount and rate of messages published
* channels - amount of active channels
* clients - amount of connected clients
* unique_clients - amount of unique clients connected
* api - count and rate of admin API calls


v0.5.1
======

* Redis engine now supports redis_url command line option

v0.5.0
======

As usual I've broken backwards compatibility again! I'm so sorry for this, but this is all for the great good.

Here is a list of changes:

* MIT license instead of BSD.
* ZeroMQ is not supported by main repository anymore. You can write your own engine though.
* Engine backends which now combine state and PUB/SUB - there are two of them: Memory engine and Redis engine.
* Engine and structure storage backend are now set up via environment variables when starting Centrifuge.
* Connection parameters must contain `timestamp` - Unix seconds as string.
* Experimental support for expiring connections. Connections can now expire if project option `connection_check` turned on.
* Centrifuge admin api can now work with list of messages instead of single one.
* Javascript client now supports message batching.
* New client API `ping` method to prevent websocket disconnects on some hosting platforms (ex. Heroku)
* New admin API `disconnect` method - disconnect user by user ID. Note, that this prevents official javascript client from reconnecting. But user can theoretically reconnect to Centrifuge immediately and his connection will be accepted. This is where connection check mechanism required.
* No more namespaces in protocol. Now namespaces are virtual - i.e. if channel name starts with `namespace_name:` then Centrifuge backend will search for its settings.
* Tornado updated to version 3.2 - this means that websockets become faster due to Tornado Websocket C module
* MongoDB and PostgreSQL structure backends must be installed from their own packages from Pypi.
* And really sweet - private channels for users without sending POST request to your web app

As you can see there are lots of important changes, so I hope you forgive me for migration inconveniences.

Migration notes:

* read updated documentation
* update Cent client to the latest version
* update javascript client to the latest version
* it's recommended to flush your structure database
* fix your configuration file to fit new changes
* `magic_project_param` configuration setting renamed to `owner_api_project_param`
* `magic_project_id` configuration setting renamed to `owner_api_project_id` - no more magic.

#### What does it mean that there are no namespaces in protocol anymore?

In the earliest versions of Centrifuge to publish message you should send something like this
via admin API:

```javascript
{"namespace": "private", "channel": "secrets", "data": {"message": "42"}}
```

Now you must do the same in this way:

```javascript
{"channel": "private:secrets", "data": {"message": "42"}}
```

I.e. like from browser.

#### Why the hell you dropped ZeroMQ support?


Because of several reasons:

* ZeroMQ is hard to configure, it has nice features like brokerless etc but I think that it is not a big win in case of using with Centrifuge.
* It's relatively slow. Redis is much much faster for real-time staff.
* To have history and presence support you will anyway need Redis.

#### How can I make private channel for user without sending POST request to my web app?

This is very simple - just add user ID as part of channel name to subscribe!

For example you have a user with ID "user42". Then private channel for him will be
`news#user42` - i.e. main channel name plus `#` separator plus user ID.

`#` in this case special symbol which tells Centrifuge that everything after it
must be interpreted as user ID which only can subscribe on this channel.

Moreover you can create a channel like `dialog#user42,user43` to create private channel
for two users.

BUT! Your fantasy here is limited by maximum channel length - 255 by default (can be changed
via configuration file option `max_channel_length`).


### Where can I found structure backends for MongoDB and PostgreSQL

MongoDB backend: https://github.com/centrifugal/centrifuge-mongodb

PostgreSQL backend: https://github.com/centrifugal/centrifuge-postgresql


v0.4.2
======

* it's now possible to specify Redis auth password for state and pubsub backends [pull request by Filip Wasilewski](https://github.com/FZambia/centrifuge/pull/23)
* it's now possible to specify PostgreSQL connection params as database url [pull request by Filip Wasilewski](https://github.com/FZambia/centrifuge/pull/24)
* now Centrifuge can be deployed on Heroku backed with Redis and PostgreSQL

The recipe of deploying Centrifuge on Heroku can be found here: https://github.com/nigma/heroku-centrifuge

The final result is available here: [centrifuge.herokuapp.com](https://centrifuge.herokuapp.com/)

v0.4.1
======

* python 3 fixes (thanks to [Filip Wasilewski](https://github.com/nigma))

v0.4.0
======

Backwards incompatible! But there is a possibility to migrate without losing your current
structure. Before updating Centrifuge go to `/dumps` location in admin interface and copy and save
output. Then update Centrifuge. Create your database from scratch. Then run Centrifuge, go to `/loads`
location and paste saved output into textarea. After clicking on submit button your previous structure
must be loaded.

Also now structure backends are classes, so you should change your configuration file according
to [current documentation](http://centrifuge.readthedocs.org/en/latest/content/configuration.html#configuration-file).

* Structure storage refactoring
* Fix API bugs when editing project ot namespace
* Node information and statistics in web interface

v0.3.8
======

Security fix! Please, upgrade to this version or disable access to `/dumps` location.

* auth now required for structure dump handler

v0.3.7
======

Backwards incompatible! Cent 0.1.3 required.

* no base64 decode for incoming API requests
* it's now possible to override sockjs-tornado settings from Centrifuge config file using `sockjs_settings` dictionary
* attempt to fix some possible races

v0.3.6
======

* handling exceptions when sending messages to client
* fix bug in application connections - which resulted in incorrect unsubscribe command behaviour

v0.3.5
======

* pyzmq 14.0.1

v0.3.4
======

* pyzmq 14.0.0
* added timestamp to message
* info connection parameter support for dom plugin
* some important fixes in documentation

v0.3.3
======

Backwards incompatible! Cent 0.1.2 required.

* extra parameter `info` to provide information about user during connect to Centrifuge.
* history messages now include all client's information
* fix Python 3 TypeError when sending message as dictionary.
* change sequence token generation steps to be more semantically correct.

This release contains important fixes and improvements. Centrifuge client must
be updated to repository version to work correctly.

Now you can provide extra parameter `info` when connecting to Centrifuge:

```javascript
var centrifuge = new Centrifuge({
    url: 'http://centrifuge.example.com',
    token: 'token',
    project: '123',
    user: '321',
    info: '{"first_name": "Alexandr", "last_name": "emelin"}'
});
```

To prevent client sending wrong `info` this JSON string must be used
while generating token:

```python
def get_client_token(secret_key, project_id, user, user_info=None):
    sign = hmac.new(six.b(str(secret_key)))
    sign.update(six.b(project_id))
    sign.update(six.b(user))
    if user_info is not None:
        sign.update(six.b(user_info))
    token = sign.hexdigest()
    return token
```

If you don't want to use `info` - you can omit this parameter. But if you omit
it make sure that it does not affect token generation - in this case you need
to generate token without `sign.update(six.b(user_info))`.


v0.3.2
======
* Base State - run single instance of Centrifuge with in-memory state storage

Now single instance of Centrifuge can work without any extra dependencies
on ZeroMQ or Redis. This can be done using Base PUB/SUB mechanism and
Base State class.

To use Base PUB/SUB mechanism you need to use `--base` command line option
when running Centrifuge's instance:

```bash
centrifuge --config=centrifuge.json --base
```

To use Base State for presence and history you should properly fill `state`
section of configuration JSON file:

```javascript
{
    "password": "admin",
    "cookie_secret": "secret",
    "api_secret": "secret",
    "state": {
        "storage": "centrifuge.state.base.State",
        "settings": {}
    }
}
```

One more time - Base options will work only when you use SINGLE INSTANCE of
Centrifuge. If you want to use several instances you need to use Redis or
ZeroMQ PUB/SUB and Redis State class (`centrifuge.state.redis.State`).

v0.3.1
======
* web interface css improvements
* fullMessage option for centrifuge.dom.js jQuery plugin
* use absolute imports instead of relative
* fix installation when set up without extra dependencies on mongodb

v0.3.0
======
* centrifuge.dom.js - jQuery plugin to add real-time even easier.
* Base Pub/Sub for single node.
* Refactor web interface, make it more mobile and human friendly, add 'actions' section to make channel operations.
* A couple of API methods to get project and namespace by name.
* fix UnicodeDecodeError in web interface.

v0.2.9
======
* fix API bug

v0.2.8
======
* experimental structure API support
* experimental Redis support for PUB/SUB
* setup.py options to build Centrifuge without ZeroMQ, PostgreSQL, MongoDB or Redis support.
* javascript client now lives on top of repo in a folder `javascript`
* rpm improvements

v0.2.7
======
* fix unique constraints for SQLite and PostgreSQL
* add client_id to default user info

v0.2.6
======
* fix handling control messages

v0.2.5
======
* fix AttributeError when Redis not configured
* doc improvements
* fix possible error in SockJS handler

v0.2.4
======
* fix unsubscribe Client method
* decouple ZeroMQ specific code into separate file
* use ":" instead of "/" as namespace and channel separator.

v0.2.3
======
* use only one ZeroMQ SUB socket for process instead of having own socket for every client.
* join/leave events for channels (structure affected).
* fix bug with Centrifuge javascript client when importing with RequireJS.
* possibility to provide structure in configuration file (useful for tests and non-dynamic structure configuration)

v0.2.2
======
* fix project settings caching in Client's instance class.
* fix unsubscribe admin API command behaviour.
* repo clean ups.

v0.2.1
======
* ping fix

v0.2.0
======
* global code refactoring.
* presence support for channels.
* history support for channels.
* Simple javascript client to communicate with Centrifuge.
* Bootstrap 3.0 for web interface.
* SQLite for structure store - now no need in installing PostgreSQL or MongoDB.
* Categories renamed into namespaces.
* Possibility to set default namespace.

v0.1.2
======
* use SockJS for admin connections instead of pure Websockets(lol, see v0.0.7)

v0.1.1
======
* Update Motor version

v0.1.0
======
* As SockJS-Tornado can handle raw websockets - WebsocketConnection class
was removed, examples and Nginx configuration updated.

v0.0.9
======
* State class to keep current application's data in memory instead of
using database queries every time.
* Small code refactoring in rpc.py

v0.0.8
======
* small admin web interface improvements

v0.0.7
======
* use Websockets in admin interface instead of SockJS

v0.0.6
======
* completely remove user management

v0.0.4
======
* changes to run on Python 3
* authentication via Github OAuth2.
* exponential backoff within tornado process.
* allow empty permissions while authentication to give full rights to client.
* PostgreSQL database support.
* different bug fixes.


v0.0.1
=====
Initial non-stable release.

