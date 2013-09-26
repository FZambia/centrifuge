#!/bin/sh
name="centrifuge"

prog="$(basename $0)"

# Source function library.
. /etc/rc.d/init.d/functions

# Also look at sysconfig; this is where environmental variables should be set on RHEL systems.
[ -f "/etc/sysconfig/$prog" ] && . /etc/sysconfig/$prog

RETVAL=0

pidfile="/var/run/centrifuge/supervisord.pid"

status() {
        /opt/centrifuge/env/bin/supervisorctl --configuration=/etc/centrifuge/supervisord.conf status
}

start() {
        echo -n $"Starting $prog: "

        if [ -f "/var/run/centrifuge/supervisord.pid" ]
        then
            echo "centrifuge seems to be running"
        else
            /opt/centrifuge/env/bin/supervisord --configuration=/etc/centrifuge/supervisord.conf
        fi
        RETVAL=$?
        echo
        [ $RETVAL = 0 ] && { success; }
        return $RETVAL
}

stop() {
        echo -n $"Stopping $prog: "
        /opt/centrifuge/env/bin/supervisorctl --configuration=/etc/centrifuge/supervisord.conf stop centrifuge all
        /opt/centrifuge/env/bin/supervisorctl --configuration=/etc/centrifuge/supervisord.conf shutdown
        [ -f "/var/run/centrifuge/supervisord.pid" ] && rm -f `cat /var/run/centrifuge/supervisord.pid`
        RETVAL=$?
        echo
}

case "$1" in
        start)
                start
        ;;
        stop)
                stop
        ;;
        status)
                status
        ;;
        restart)
                stop
                start
        ;;
        *)
                echo $"Usage: $0 {start|stop|restart|status}"
                RETVAL=2
esac

exit $RETVAL