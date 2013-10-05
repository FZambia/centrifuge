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
