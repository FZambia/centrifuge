#!/bin/sh
name="centrifuge"

prog="$(basename $0)"

# Source function library.
. /etc/rc.d/init.d/functions

[ -f "/etc/sysconfig/$prog" ] && . /etc/sysconfig/$prog

RETVAL=0

start() {
        echo -n $"Starting $prog: "
        /opt/centrifuge/env/bin/supervisorctl start centrifuge all
        RETVAL=$?
        echo
        return $RETVAL
}

stop() {
        echo -n $"Stopping $prog: "
        /opt/centrifuge/env/bin/supervisorctl stop centrifuge all
        RETVAL=$?
        echo
}

rh_status() {
        echo "use supervisor to check status"
}

case "$1" in
        start)
                rh_status > /dev/null 2>&1 && exit 0
                start
        ;;
        stop)
                stop
        ;;
        status)
                /opt/centrifuge/env/bin/supervisorctl centrifuge status
                RETVAL=$?
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