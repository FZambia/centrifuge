Installation
============

.. _install:


Centrifuge works on Linux and Mac OS X only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have machine with those operating systems installed then you are ready to go.


Centrifuge also requires python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Python 2.6, Python 2.7 or Python 3.3 required.

You can find nice guide about how to install Python on Mac OS X and Linux 
`here <https://python-guide.readthedocs.org/en/latest/starting/install/osx/>`_ and
`here <https://python-guide.readthedocs.org/en/latest/starting/install/linux/>`_ respectively


Use Python's virtualenv
~~~~~~~~~~~~~~~~~~~~~~~

To isolate Centrifuge's environment it is recommended to use virtualenv.
If you are not familiar with it yet - please, make time and read about it
`here <https://python-guide.readthedocs.org/en/latest/dev/virtualenvs/>`_

.. code-block:: bash

    virtualenv --no-site-packages centrifuge/env
    . centrifuge/env/bin/activate


Of course, you can name folders as you like. This is just an example.


Install Centrifuge
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    pip install centrifuge

If you get exception like:

.. code-block:: bash

    Error: pg_config executable not found.

Then you don't have `libpq-dev` package installed on your machine. For example, for Debian:

.. code-block:: bash

    sudo apt-get install libpq-dev

Or for Red Hat:

.. code-block:: bash

    yum install postgresql-devel


If you get errors while building pyzmq you may need to install ``libzmq`` on your system first:

.. code-block:: bash

    apt-get install libzmq3-dev


Or for Red Hat:

.. code-block:: bash

    yum install zeromq3


Also if you have problems with installing Centrifuge on Python 3.3 or later, make sure you have `distribute`
installed:

.. code-block:: bash

    curl -O http://python-distribute.org/distribute_setup.py
    python distribute_setup.py
    easy_install pip


From version ``0.2.8`` there is experimental Redis PUB/SUB support in Centrifuge. This means that you
can run Centrifuge using Redis instead of ZeroMQ. In this case you can even build Centrifuge without
extra dependency on ZeroMQ libraries.

.. code-block:: bash

    python setup.py install --without-zmq


If you don't need MongoDB or PostgreSQL for structure storing you can also remove dependencies on them
using:

.. code-block:: bash

    python setup.py install --without-postgresql --without-mongodb

Finally if you don't need Redis for PUB/SUB or presence/history data, you can build Centrifuge
without dependencies on Redis packages:

.. code-block:: bash

    python setup.py install --without-redis


Structure database
~~~~~~~~~~~~~~~~~~

Centrifuge by default uses SQLite as structure store. It does not require installation
because SQLite comes with standard Python library.

You can also use `MongoDB <http://docs.mongodb.org/manual/>`_ as data
store. `Here <http://docs.mongodb.org/manual/installation/>`_ is explanation
how to install it on your system.

And if you want you can also run Centrifuge with `PostgreSQL <http://www.postgresql.org/>`_
as storage. Read `this <http://wiki.postgresql.org/wiki/Detailed_installation_guides>`_ for help with
PostgreSQL installation.


Configuration file
~~~~~~~~~~~~~~~~~~

Configuration is a JSON file. You can find example of those file in Centrifuge's
repository. With SQLite (installed with default settings) configuration file
can be omitted during development. But in production environment it must be used
because it contains important security settings like cookie_secret and administrative
password.

More about configuration see in special documentation chapter.


Finally run Centrifuge
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    centrifuge --config=/path/to/your/configuration/json/file


Go to http://localhost:8000/ and make sure that it is running.


Congratulations, we are done here!