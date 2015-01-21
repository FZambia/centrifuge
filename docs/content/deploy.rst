Deployment
==========

.. _deploy:

Nginx configuration
~~~~~~~~~~~~~~~~~~~

Minimal Nginx version - 1.3.13

Here is an example Nginx configuration to deploy Centrifuge.

.. code-block:: bash

    #user nginx;
    worker_processes 4;

    #error_log /var/log/nginx/error.log;

    events {
        worker_connections 1024;
        #use epoll;
    }

    http {
        # Enumerate all the Tornado servers here
        upstream centrifuge {
            #sticky;
            ip_hash;
            server 127.0.0.1:8000;
            #server 127.0.0.1:8001;
            #server 127.0.0.1:8002;
            #server 127.0.0.1:8003;
        }
        include mime.types;
        default_type application/octet-stream;

        keepalive_timeout 65;
        proxy_read_timeout 200;
        sendfile on;
        tcp_nopush on;
        tcp_nodelay on;
        gzip on;
        gzip_min_length 1000;
        gzip_proxied any;

        # Only retry if there was a communication error, not a timeout
        # on the Tornado server (to avoid propagating "queries of death"
        # to all frontends)
        proxy_next_upstream error;

        map $http_upgrade $connection_upgrade {
            default upgrade;
            ''      close;
        }

        server {
            listen 8081;
            server_name localhost;

            location /static/ {
                root /var/www/different/python/centrifuge/src/src/centrifuge/frontend;
            }
            location = /favicon.ico {
                rewrite (.*) /static/favicon.ico;
            }
            location = /robots.txt {
                rewrite (.*) /static/robots.txt;
            }
            location / {
                proxy_pass_header Server;
                proxy_set_header Host $http_host;
                proxy_redirect off;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Scheme $scheme;
                proxy_pass http://centrifuge;
            }
            location /socket {
                proxy_buffering off;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Scheme $scheme;
                proxy_pass http://centrifuge;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection $connection_upgrade;
            }
            location /connection/websocket {
                proxy_buffering off;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Scheme $scheme;
                proxy_pass http://centrifuge;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection $connection_upgrade;
            }
            location /connection {
                proxy_buffering off;
                proxy_set_header X-Real-IP $remote_addr;
                proxy_set_header X-Scheme $scheme;
                proxy_pass http://centrifuge;
                proxy_http_version 1.1;
                proxy_set_header Upgrade $http_upgrade;
                proxy_set_header Connection $connection_upgrade;
            }
        }
    }


Look carefully at commented ``sticky;`` directive in upstream section.

In this configuration example we use ``ip_hash`` directive to proxy client with the same ip
address to the same backend process. This is very important when we have several processes.

When client connects to Centrifuge - session created - and to communicate those client must
send all next requests to the same backend process. But ``ip_hash`` is not the best choice
in this case, because there could be situations where a lot of different browsers are coming
with the same IP address (behind proxies) and the load balancing system won't be fair.
Also fair load balancing does not work during development - when all clients connecting from
localhost.

So best solution would be using something like `nginx-sticky-module <http://code.google.com/p/nginx-sticky-module/>`_
which uses a cookie to track the upstream server for making each client unique.


Supervisord configuration example
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. _supervisord_configuration:

In 'deploy' folder of Centrifuge's repo you can find supervisord configuration
example. Something like this:


centrifuge.conf (put it into ``/etc/supervisor/conf.d/centrifuge.conf``)

.. code-block:: bash

    [program:centrifuge]
    process_name = %(process_num)s
    environment=PYTHONPATH="/opt/centrifuge/src",CENTRIFUGE_STORAGE="sqlite"
    directory = /opt/centrifuge/src
    command = /opt/centrifuge/env/bin/python /opt/centrifuge/src/centrifuge/node.py --log_file_prefix=/var/log/centrifuge/centrifuge-%(process_num)s.log --config=/etc/centrifuge/centrifuge.json --port=%(process_num)s --path=/var/db/centrifuge/centrifuge.sqlite
    numprocs = 1
    numprocs_start = 8000
    user = centrifuge


Centos 6
~~~~~~~~

`In repository <https://github.com/centrifugal/centrifuge/tree/master/deploy>`_  you can find everything to build rpm for Centos 6.

If you are not a Centos 6 user you can find a lot of useful things there, which were successfully tested in production environment.

Heroku
~~~~~~

Centrifuge can be deployed on Heroku. Note that Heroku disables inactive WebSocket connections
after 55 sec, so you need to implement some sort of ping on client side. There is an example
in Centrifuge repo - simple chat on JSFiddle using Centrifuge hosted on Heroku.

The recipe of deploying Centrifuge on Heroku can be found here: https://github.com/centrifugal/heroku-centrifuge

The final result is available here: `centrifuge.herokuapp.com <https://centrifuge.herokuapp.com/>`_ (password = ``password``)
