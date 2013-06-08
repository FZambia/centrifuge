Supervisord configuration example
=================================

.. _supervisord_configuration:

In 'deploy' folder of Centrifuge's repo you can find supervisord configuration
example. Something like this:

supervisord.conf:

.. code-block:: bash

    [unix_http_server]
    file=/tmp/supervisor.sock

    [inet_http_server]
    port=127.0.0.1:9001

    [supervisord]
    logfile=/tmp/supervisord.log
    pidfile=/tmp/supervisord.pid

    [rpcinterface:supervisor]
    supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

    [include]
    files = *.supervisor


centrifuge.supervisor

.. code-block:: bash

    [program:centrifuge]
    process_name = centrifuge-%(process_num)s
    command = centrifuge --conf=%(here)s/../src/config.json --port=%(process_num)s --log_file_prefix=/tmp/%(program_name)s-%(process_num)s.log
    numprocs = 1
    numprocs_start = 8000