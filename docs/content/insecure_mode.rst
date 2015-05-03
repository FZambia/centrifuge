Insecure mode
=============

.. _insecure_mode:


Version 0.7.0 of Centrifuge introduced new insecure mode.

To start Centrifuge in this mode use ``CENTRIFUGE_INSECURE`` environment variable:

.. code-block:: bash

    CENTRIFUGE_INSECURE=1 centrifuge --logging=debug --debug --config=config.json


You can also set ``insecure`` option to ``true`` in configuration file to do the same.

Insecure mode:

- disables client timestamp and token check
- allows anonymous access for all channels
- allows client to publish into all channels
- suppresses connection check

When using insecure mode you can create client connection in this way:

.. code-block:: javascript

    var centrifuge = new Centrifuge({
        "url": url,
        "project": project,
        "insecure": true
    });

Note that there is no ``token``, ``user`` and ``timestamp`` parameters so you can connect
to Centrifuge without any backend code.

This allows to use Centrifuge as a quick and simple solution when making real-time demos,
presentations, testing ideas etc. But this is only for personal demonstration use cases -
this mode should never work in production until you really want it to be there.

Look at `demo <https://github.com/centrifugal/centrifuge/tree/master/examples/insecure_mode>`_ to see insecure mode in action.
