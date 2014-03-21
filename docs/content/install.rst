Installation
============

.. _install:

Centrifuge was developed and tested on Linux and Mac OS X operating systems. The work on
other systems is not guaranteed.

It is written on Python. Python 2.6, Python 2.7 or Python 3.3 are supported.

You can find nice guide about how to install Python on Mac OS X or Linux
`here <https://python-guide.readthedocs.org/en/latest/starting/install/osx/>`_ and
`here <https://python-guide.readthedocs.org/en/latest/starting/install/linux/>`_ respectively

To isolate Centrifuge environment it is recommended to use virtualenv.
If you are not familiar with it yet - please, make time and read about it
`here <https://python-guide.readthedocs.org/en/latest/dev/virtualenvs/>`_

.. code-block:: bash

    virtualenv --no-site-packages centrifuge/env
    . centrifuge/env/bin/activate


Of course, you can name folders as you like. This is just an example.

.. code-block:: bash

    pip install centrifuge


Also if you have problems with installing Centrifuge on Python 3.3 or later, make sure you have `pip`
installed:

.. code-block:: bash

    curl -O http://python-distribute.org/distribute_setup.py
    python distribute_setup.py
    easy_install pip


Now you can run centrifuge:

.. code-block:: bash

    centrifuge


Custom options can be set using configuration JSON file. You can find example of those
file in Centrifuge's repository. During development configuration file can be omitted.
But in production it must be used because it contains important security settings like
cookie_secret, administrative password etc.

Go to http://localhost:8000/ and make sure that it is running.

