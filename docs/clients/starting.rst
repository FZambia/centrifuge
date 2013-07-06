Overview
========

.. _client_overview:

There are two ways to communicate with Centrifuge from browser. First, you can use
pure Websockets. Second, SockJS library - ['websocket', 'xdr-streaming', 'xhr-streaming',
'iframe-eventsource', 'iframe-htmlfile', 'xdr-polling', 'xhr-polling', 'iframe-xhr-polling',
'jsonp-polling'] can be used.

To use pure WebSocket endpoint you should initialize connection like this:

.. code-block:: js

    connection = new WebSocket('ws://{{centrifuge_address}}/connection/websocket');


When using SockJS library initialize connection like this:

.. code-block:: js

    connection = new SockJS('http://{{centrifuge_address}}/connection', null, {
        protocols_whitelist: [
            'websocket',
            'xdr-streaming',
            'xhr-streaming',
            'iframe-eventsource',
            'iframe-htmlfile',
            'xdr-polling',
            'xhr-polling',
            'iframe-xhr-polling',
            'jsonp-polling'
        ]
    });


At this moment there are no javascript libraries to wrap communication routine
with Centrifuge. But communication is rather simple.

You should know only 4 basic commands:

1) auth
2) subscribe
3) unsubscribe
4) broadcast

Lets see on them in detail.


Auth
----

Once your application established Websocket or SockJS connection with Centrifuge
client should send authorization request.

.. code-block:: js

    var auth_message = {
        'method': 'auth',
        'params': {
            'token': '{{auth_data["token"]}}',
            'user': '{{auth_data["user"]}}',
            'project_id': '{{auth_data["project_id"]}}',
            'permissions': {}
        }
    };

    connection.send(JSON.stringify(auth_message))


token - token generated from project_id and project's secret key. Used to
make sure that connected client belongs to your application.

user - this string is user's unique identity. It is used when Centrifuge checks
user's permissions sending POST request with connection data to your web app.

project_id - this is just project id from admin's interface

permissions - this is an object which is used to set certain permissions for
current client. Empty objects means that user will be able to listen or send
data to every category and every channel of this project's space.


Subscribe
---------

After successful authentication client can subscribe on channel he is interested
in:

.. code-block:: js

    var subscribe_message = {
        'method': 'subscribe',
        'params': {
            'to': {
                'python': ['django']
            }
        }
    };
    connection.send(JSON.stringify(subscribe_message));


In this case "python" is a category and "django" is channel name. Subscribe request
must contain at least one channel in some category to subscribe.


Unsubscribe
-----------

If you want to unsubscribe from some channels - send message like this:

.. code-block:: js

    var unsubscribe_message = {
        'method': 'unsubscribe',
        'params': {
            'from': {
                'python': ['django']
            }
        }
    };
    connection.send(JSON.stringify(unsubscribe_message));


Broadcast
---------

Clients can send messages in bidirectional categories. Here is an example of broadcast message:

.. code-block:: js

    var broadcast_message = {
        'method': 'broadcast',
        'params': {
            'category': 'python',
            'channel': 'django',
            'data': {'input': input.val()}
        }
    };
    connection.send(JSON.stringify(broadcast_message));


Look - you send category name, channel name and data of this new message (event).
Data must be object.
