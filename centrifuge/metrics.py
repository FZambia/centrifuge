# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

import six
import time
import socket
import logging
from functools import wraps
from collections import defaultdict


logger = logging.getLogger('metrics')


class MetricError(Exception):
    pass


class Timer(object):
    """
    Measure time interval between events
    """

    def __init__(self, collector, metric):
        self.collector = collector
        self.metric = metric
        self.interval = None
        self._sent = False
        self._start_time = None

    def __call__(self, f):
        @wraps(f)
        def wrapper(*args, **kw):
            with self:
                return f(*args, **kw)
        return wrapper

    def __enter__(self):
        return self.start()

    def __exit__(self, t, val, tb):
        self.stop()

    def start(self):
        self.interval = None
        self._sent = False
        self._start_time = time.time()
        return self

    def stop(self, send=True):
        if self._start_time is None:
            raise MetricError("Can not stop - timer not started")
        delta = time.time() - self._start_time
        self.interval = int(round(1000 * delta))  # to milliseconds.
        if send:
            self.send()
        return self.interval

    def send(self):
        if self.interval is None:
            raise MetricError('No time interval recorded')
        if self._sent:
            raise MetricError('Already sent')
        self._sent = True
        self.collector.timing(self.metric, self.interval)


class Collector(object):
    """
    Class to collect and aggregate statistical metrics.
    Lots of ideas and some code borrowed from Statsd server/client
    implementations and adapted to use with Centrifuge.
    """
    SEP = '.'

    def __init__(self, sep=None):
        self.sep = sep or self.SEP
        self._counters = None
        self._times = None
        self._gauges = None
        self._last_reset = None
        self.reset()

    def get(self):
        prepared_data = self.prepare_data()
        self.reset()
        return prepared_data

    def prepare_data(self):
        timestamp = time.time()
        to_return = {}

        for metric, value in six.iteritems(self._counters):
            to_return[metric + self.sep + 'count'] = value
            to_return[metric + self.sep + 'rate'] = round(value / (timestamp - self._last_reset), 2)

        for metric, value in six.iteritems(self._gauges):
            to_return[metric] = value

        for metric, intervals in six.iteritems(self._times):
            prepared_timing_data = self.prepare_timing_data(intervals)
            for key, value in six.iteritems(prepared_timing_data):
                to_return[metric + self.sep + key] = value

        return to_return

    @classmethod
    def prepare_timing_data(cls, intervals):
        min_interval = intervals[0]
        max_interval = 0
        avg_interval = 0
        total = 0
        count = 0
        for interval in intervals:
            interval = float(interval)
            count += 1
            total += interval
            if interval > max_interval:
                max_interval = interval
            if interval < min_interval:
                min_interval = interval
        if count:
            avg_interval = round(total / count, 2)

        return {
            "min": min_interval,
            "max": max_interval,
            "avg": avg_interval,
            "count": count
        }

    def reset(self):
        self._counters = defaultdict(int)
        self._times = defaultdict(list)
        self._gauges = defaultdict(int)
        self._last_reset = time.time()

    def timing(self, metric, interval):
        if metric not in self._times:
            self._times[metric] = []
        self._times[metric].append(interval)

    def increment(self, metric, incr_by=1):
        if metric not in self._counters:
            self._counters[metric] = 0
        self._counters[metric] += incr_by

    incr = increment

    def decrement(self, metric, decr_by=1):
        self.incr(metric, -decr_by)

    decr = decrement

    def gauge(self, metric, value):
        self._gauges[metric] = value

    def get_timer(self, time_name, start=True):
        timer = Timer(self, time_name)
        if start:
            return timer.start()
        return timer


class Exporter(object):
    """
    Export collected metrics into Graphite
    """

    SEP = "."

    def __init__(self, host, port, prefix=None, sep=None, max_udp_size=512):
        self.host = host
        self.port = port
        self.prefix = prefix or ""
        self.sep = sep or self.SEP
        self._address = (socket.gethostbyname(host), port)
        self.max_udp_size = max_udp_size
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.socket.setblocking(0)

    def get_key(self, metric):
        if not self.prefix:
            return metric
        if self.prefix.endswith(self.sep):
            return self.prefix + metric
        else:
            return self.prefix + self.sep + metric

    def prepare_metrics(self, metrics):
        to_return = []
        timestamp = int(time.time())
        for metric, value in six.iteritems(metrics):
            to_return.append('{0} {1} {2}'.format(self.get_key(metric), int(value), timestamp))
        return to_return

    def export(self, metrics):
        if not metrics:
            return

        prepared_metrics = self.prepare_metrics(metrics)

        data = prepared_metrics.pop(0)
        while prepared_metrics:
            stat = prepared_metrics.pop(0)
            if len(stat) + len(data) + 1 >= self.max_udp_size:
                self.send(data)
                data = stat
            else:
                data += '\n' + stat

        self.send(data)

    def send(self, data):
        try:
            self.socket.sendto(data.encode('ascii'), self._address)
        except Exception as err:
            logger.exception(err)
