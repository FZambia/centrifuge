Engines
=======

.. _engines:


Engine in Centrifuge is a class responsible for managing subscriptions, publishing
messages into appropriate channels, handling published messages, handling presence
and history information.

Centrifuge has 2 built-in engines - in Memory engine and Redis engine. By default
Memory engine is used.

To set engine you should use ``CENTRIFUGE_ENGINE`` environment variable.

Available values are ``memory``, ``redis`` or python path to custom engine:

Memory engine:

.. code-block:: bash

    CENTRIFUGE_ENGINE=memory centrifuge --config=config.json

Redis engine:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --config=config.json

Redis engine using path to class:

.. code-block:: bash

    CENTRIFUGE_ENGINE="centrifuge.engine.redis.Engine" centrifuge --config=config.json


Memory engine
~~~~~~~~~~~~~

Supports only one node. Nice choice to start with. Supports all features keeping
everything in process memory.


Redis engine
~~~~~~~~~~~~

Allows scaling Centrifuge running multiple processes on same or different machine.
Keeps presence and history data in Redis, uses redis PUB/SUB to support running
multiple instances of Centrifuge. Also it allows to call API commands.

See available redis engine specific options using ``--help``:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --help


How to publish via Redis engine API listener? Start Centrifuge with Redis
engine and ``--redis_api`` option:

.. code-block:: bash

    CENTRIFUGE_ENGINE=redis centrifuge --logging=debug --config=config.json --redis_api


Then use Redis client for your favorite language, ex. for Python:

.. code-block:: python

    import redis
    import json

    client = redis.Redis()

    to_send = {
        "project": "development",
        "data": [
            {
                "method": "publish",
                "params": {"channel": "$public:chat", "data": {"input": "hello"}}
            },
            {
                "method": "publish",
                "params": {"channel": "events", "data": {"event": "message"}}
            },
        ]
    }

    client.rpush("centrifuge.api", json.dumps(to_send))


So you send JSON object with project ID as a value for ``project`` key and list
of commands as a value for ``data`` key.

Note again - you don't have response here. If you need to check response - you
should use HTTP API.

``publish`` is the most usable command in Centrifuge so Redis API listener was
invented with primary goal to reduce HTTP overhead when publishing quickly.
This can also help using Centrifuge with other languages for which we don't
have HTTP API client yet.