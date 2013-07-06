Installation
============

.. _install:


Centrifuge works on Linux and Mac OS X only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have machine with those operating systems installed then you are ready to go.


Centrifuge also requires python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Python 2.6 and Python 2.7 are optimal. It's designed to run on python 3.3 too,
but not heavily tested yet.

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


Install Centrifuge from pip
~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    pip install centrifuge

If you get exception like:

.. code-block:: bash

    Error: pg_config executable not found.

Then you don't have `libpq-dev` package installed on your machine. For example, for Debian:

.. code-block:: bash

    sudo apt-get install libpq-dev


Also if you have problems with installing Centrifuge on Python 3, make sure you have `distribute`
installed:

.. code-block:: bash

    curl -O http://python-distribute.org/distribute_setup.py
    python distribute_setup.py
    easy_install pip


Install and run database
~~~~~~~~~~~~~~~~~~~~~~~

Centrifuge by default uses `MongoDB <http://docs.mongodb.org/manual/>`_ as data
store.

`Here <http://docs.mongodb.org/manual/installation/>`_ is explanation
how to install it on your system.

You can also run Centrifuge with `PostgreSQL <http://www.postgresql.org/>`_ as storage.

Read `this <http://wiki.postgresql.org/wiki/Detailed_installation_guides>`_ for help with
PostgreSQL installation.

To use custom connection settings to storage you should fill appropriate section of
configuration file.


Fill centrifuge's configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration is a JSON file. You can find example of those file in Centrifuge's
repository. With MongoDB (installed with default settings) configuration file
can be omitted during development. But in production environment it must be used
because it contains important security settings like cookie_secret and administrative
password.

More about configuration see in special documentation chapter.


Finally run Centrifuge
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    centrifuge --config=/path/to/your/configuration/json/file


Go to http://localhost:8000/ and make sure that it is running.


Congratulations, we are done!