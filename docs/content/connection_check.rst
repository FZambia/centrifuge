Connection check
================

.. _connection_check:


This mechanism was introduced in Centrifuge 0.7.0

Before 0.7.0 Centrifuge had another connection check mechanism which was unreasonably
difficult.

When client connects to Centrifuge with proper connection credentials his connection
can live forever. This means that even if you banned this user in your web application
he will be able to read messages from channels he already subscribed to. It's not
desirable in some cases.

Project settings has two special options: ``connection_check`` and ``connection_lifetime``.
Connection check is turned off by default so if you need it you must turn it on in
project settings.

Connection lifetime is a time in seconds how long connection will be valid after successful
connect. When connection lifetime expires Centrifuge will send a signal to javascript client
and it will make an AJAX POST request to your web application. By default this request goes
to ``/centrifuge/refresh`` url endpoint. You can change it using javascript option
``refreshEndpoint``. In response your server must return JSON with connection credentials:

.. code-block:: python

        to_return = {
            'project': "PROJECT ID",
            'user': "USER ID,
            'timestamp': "CURRENT TIMESTAMP AS INTEGER",
            'info': "ADDITIONAL CONNECTION INFO",
            'token': "TOKEN BASED ON PARAMS ABOVE",
        }
        return json.dumps(to_return)

You should just return the same connection credentials when rendering page initially.
Just with current timestamp. Centrifuge javascript client will then send them to
Centrifuge and connection will be refreshed for a connection lifetime period.

If you don't want to refresh connection for this user - just return 403 Forbidden
on refresh request.