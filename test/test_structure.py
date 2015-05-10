# coding: utf-8
from __future__ import print_function
from unittest import TestCase, main
from centrifuge.structure import validate_and_prepare_project_structure


class StructureTest(TestCase):

    def test_dict_options(self):
        config = {
          "password": "password",
          "cookie_secret": "cookie_secret",
          "structure": [
            {
              "name": "development",
              "secret": "secret",
              "namespaces": [
                {
                  "name": "public",
                  "publish": True,
                  "watch": True,
                  "presence": True,
                  "join_leave": True,
                  "history_size": 10,
                  "history_lifetime": 30
                }
              ]
            }
          ]
        }
        validate_and_prepare_project_structure(config["structure"])


if __name__ == '__main__':
    main()
