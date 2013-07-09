Command line options
====================

.. _cli:

Centrifuge has some command line arguments.


Example. To create 2 instances of Centrifuge you can use something like this:


.. code-block:: bash

    centrifuge --port=8000 --zmq_pub_port=7000 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001
    centrifuge --port=8001 --zmq_pub_port=7001 --zmq_sub_address=tcp://localhost:7000,tcp://localhost:7001


To run Centrifuge in debug Tornado's mode:

.. code-block:: bash

    centrifuge --debug


To run Centrifuge with XPUB/XSUB proxy:

.. code-block:: bash

    centrifuge --zmq_pub_sub_proxy --zmq_xsub=tcp://localhost:6000 --zmq_xpub=tcp://localhost:6001


But in case of using XPUB/XSUB proxy you should actually start this proxy:

.. code-block:: bash

    xpub_xsub --xsub=tcp://*:6000 --xpub=tcp://*:6001


Using XPUB/XSUB proxy is nice because you don't need to restart all your Centrifuge processes
when you add new one, but it's a single point of failure. Remember about it.

There is also XPUB/XSUB proxy implemented in Go lang: `gist on Github <https://gist.github.com/FZambia/5955032>`_