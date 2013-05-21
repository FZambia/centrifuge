Creating new project
====================

.. _create project:


When you have running Centrifuge's instance and want to create web application using it -
first you should do is to add your project into Centrifuge. It's very simple - just fill
the form.

.. image:: project_create_form.png
    :width: 650 px

**name** - unique project name, must be written using ascii symbols only. This is project
slug, human-readable identity.

**display_name** - project's name in web interface. If empty - `name` will be used.

**description** - project's extended description

**validate_url** - url for authorization purposes, when your web application's client
joins to Centrifuge - you can provide user id. Also you must provide permissions for
every connected user. More about user id and permissions later. Anyway this is an address
of your web application that will be used to authorize new client's connection. Centrifuge
sends POST request with user id and permissions to this url and your application must decide
to allow authorization or not.

**auth_attempts** - amount of attempts Centrifuge will try to validate user's permissions
sending POST request to `validate_url`

**back_off_interval** - at the moment when Centrifuge restarts your web application can
have lots of active connected clients. All those client will reconnect and Centrifuge will
send authorization request to your web application's `validate_url`. For such cases Centrifuge
has [exponential backoff](http://en.wikipedia.org/wiki/Exponential_backoff) support to reduce
load on your application.

**back_off_max_timeout** - maximum time for backoff timeout (time before client connects to
Centrifuge and sending authorization request to `validate_url`).


So project created, we are ready to continue.