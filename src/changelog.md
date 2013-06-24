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
