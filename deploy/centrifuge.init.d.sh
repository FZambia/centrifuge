#!/bin/sh
name="cyclone_sse"

# exchange sync daemon startup script
#
# chkconfig: - 85 15
# processname: $prog
# config: /etc/sysconfig/$prog
# pidfile: /var/run/$prog.pid
# description: $prog

prog="$(basename $0)"

# Source function library.
. /etc/rc.d/init.d/functions

[ -f "/etc/sysconfig/$prog" ] && . /etc/sysconfig/$prog

pidfile="/var/run/${prog}.pid"
lockfile="/var/lock/subsys/${prog}"
uid=`id -u ${name}`
gid=`id -g ${name}`
cyclone_sse_options=`cat /etc/${name}/cyclone_sse.conf`

export PYTHONPATH=/opt/cyclone_sse/src
opts="/opt/cyclone_sse/env/bin/twistd --uid=${uid} --gid=${gid} --pidfile=${pidfile} --logfile=/var/log/${prog}.log cyclone-sse ${cyclone_sse_options}"


RETVAL=0

start() {
        echo -n $"Starting $prog: "
        ${opts}
        RETVAL=$?
        echo
        [ $RETVAL = 0 ] && touch ${lockfile}
        return $RETVAL
}

stop() {
        echo -n $"Stopping $prog: "
        killproc -p ${pidfile} ${prog}
        RETVAL=$?
        echo
        [ $RETVAL = 0 ] && rm -f ${lockfile} ${pidfile}
}

rh_status() {
        status -p ${pidfile} ${prog}
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
                rh_status
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