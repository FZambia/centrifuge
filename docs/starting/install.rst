Installation
============

.. _install:


Centrifuge works on Linux and Mac OS X only
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

If you have machine with those operating systems installed then you are ready to go.


Centrifuge also requires python
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Python 2.6 and Python 2.7 are optimal. It's designed to run on python 3.3 too,
but not tested yet.

You can find nice guide about how to install Python on Mac OS X and Linux 
`here <https://python-guide.readthedocs.org/en/latest/starting/install/osx/>`_ and
`here <https://python-guide.readthedocs.org/en/latest/starting/install/linux/>`_ respectively


Clone repo
~~~~~~~~~~

.. code-block:: bash

    mkdir centrifuge
    git clone https://github.com/FZambia/centrifuge.git centrifuge/src/


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


Install and run MongoDB
~~~~~~~~~~~~~~~~~~~~~~~

Centrifuge uses `MongoDB <http://docs.mongodb.org/manual/>`_ as data
store.

`Here <http://docs.mongodb.org/manual/installation/>`_ is explanation
how to install it on your system.


Fill centrifuge's configuration file
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Configuration is a JSON file. You can find example of those file in
Centrifuge's repository.

More about configuration see in special documentation chapter.


Finally run Centrifuge
~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

    centrifuge


Go to http://localhost:8000/ and make sure that it is running.


Congratulations, we are done!