# coding: utf-8
from unittest import TestCase, main
import sys
import os

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)

from centrifuge.core import *


class CoreTest(TestCase):

    def setUp(self):

        self.project_id = 'test'
        self.category = 'test'
        self.channel = 'test'


if __name__ == '__main__':
    main()