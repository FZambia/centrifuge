Logging in
==========

.. _login:

You can log into Centrifuge using your Google account.

Also there is Github OAUTH support. To authenticate with GitHub, first register
your Centrifuge installation at https://github.com/settings/applications/new to get
the client ID and secret. After this add following settings to your configuration
file

.. code-block:: javascript
    {
        ...
        "auth_github": true,
        "github_client_id": "github_client_id",
        "github_client_secret": "github_client_secret"
        '''
    }