Command line options
====================

.. _cli:

Centrifuge has some command line arguments.


Example. To create 2 instances of Centrifuge you can use something
like this:


.. code-block:: bash

    centrifuge --port=8000 --zmq_pub_port=7000 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001
    centrifuge --port=8001 --zmq_pub_port=7001 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001