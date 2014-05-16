# coding: utf-8
from unittest import TestCase, main
import time


from centrifuge.metrics import *


class CollectorTest(TestCase):

    def setUp(self):
        self.collector = Collector()

    def test_timer(self):
        timer = self.collector.get_timer('test')
        time.sleep(0.1)
        interval = timer.stop()
        self.assertTrue(interval >= 0.1)
        metrics = self.collector.get()
        self.assertTrue('test.avg') in metrics
        self.assertTrue('test.min') in metrics
        self.assertTrue('test.max') in metrics
        self.assertTrue('test.count') in metrics

    def test_counter(self):
        self.collector.incr('counter')
        self.collector.incr('counter', 5)
        self.collector.decr('counter', 2)
        metrics = self.collector.get()
        self.assertEqual(metrics['counter.count'], 4)
        self.assertTrue('counter.rate' in metrics)

    def test_gauge(self):
        self.collector.gauge('gauge', 101)
        metrics = self.collector.get()
        self.assertEqual(metrics['gauge'], 101)


if __name__ == '__main__':
    main()