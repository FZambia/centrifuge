Web interface
=============

.. _web_interface:


Centrifuge comes with administrative web interface.

Using it you can create, edit or delete projects, namespaces, publish
JSON messages into channels etc.

Also you can watch for new messages in your projects in real-time.

.. image:: img/main.png
    :width: 650 px


Logging in
~~~~~~~~~~

.. _login:

You can log into Centrifuge using **password** from configuration file.

If you did not set password in configuration file - you will be log in as
administrator automatically. But remember that this is normal only for
development stage. In production you must use strong password.


Creating new project
~~~~~~~~~~~~~~~~~~~~

.. _create project:


When you have running Centrifuge's instance and want to create web application using it -
first you should do is to add your project into Centrifuge. It's very simple - just fill
the form.

**name** - unique project name, must be written using ascii symbols only. This is project
slug, human-readable identity.

**display name** - project's name in web interface.

**auth address** - url for authorization purposes, when your web application's client
joins to Centrifuge - you can provide user id. Also you must provide permissions for
every connected user. More about user id and permissions later. Anyway this is an address
of your web application that will be used to authorize new client's connection. Centrifuge
sends POST request with user id and permissions to this url and your application must decide
to allow authorization or not.

**max auth attempts** - amount of attempts Centrifuge will try to validate user's permissions
sending POST request to ``auth address``

**back off interval** - at the moment when Centrifuge restarts your web application can
have lots of active connected clients. All those client will reconnect and Centrifuge will
send authorization request to your web application's ``auth address``. For such cases Centrifuge
has `exponential back-off <http://en.wikipedia.org/wiki/Exponential_backoff>`_ support to reduce
load on your application. This is time of back of minimum interval in milliseconds.

**back off max timeout** - maximum time in milliseconds for backoff timeout (time before client
connects to Centrifuge and sending authorization request to ``auth address``).


So project created, we are ready to continue.


Project management
~~~~~~~~~~~~~~~~~~

.. _project settings:


Project management has several panels to control project:

1) **General**

Here you can see project credentials and regenerate project **secret key**.
Secret key - is a key for signing all API requests to Centrifuge.

You can also manage **namespaces**. Namespace is a way to customize channel
properties. You create namespace with certain options and then each channel
which belongs to this namespace will have those options.

2) **Edit**

Here you can edit project options you set during creating project.

Also from this tab project can be deleted.

3) **Actions**

Manage your channels from web interface. You can request presence or history info
from here, publish new message into channel or unsubscribe user from channel by user ID.


Namespace management
~~~~~~~~~~~~~~~~~~~~

.. _namespace_settings:

Centrifuge allows to configure channel's settings using namespaces.

You can create new namespace, configure its settings and after that every
channel which belongs to this namespace will have those settings. It's flexible and
provides a great control over channel behaviour.
