# coding: utf-8
from unittest import TestCase, main
import sys
import os

path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, path)

from centrifuge.schema import req_schema, admin_params_schema,\
    client_params_schema
from jsonschema import validate, ValidationError


class SchemaTest(TestCase):

    def setUp(self):

        pass

    def test_req_schema(self):
        schema = {
            'id': '123',
            'method': 'test',
            'params': {"test": "test"}
        }

        self.assertEqual(validate(schema, req_schema), None)

    def test_admin_params_schema_broadcast(self):
        schema = {
            "namespace": "test",
            "channel": "test",
            "data": {"input": "test"}
        }

        self.assertEqual(
            validate(schema, admin_params_schema["publish"]),
            None
        )

        del schema["namespace"]

        self.assertEqual(
            validate(schema, admin_params_schema["publish"]),
            None
        )

    def test_admin_params_schema_unsubscribe(self):
        schema = {
            "user": "test",
            "namespace": "channel",
            "channel": "test"
        }

        self.assertEqual(
            validate(schema, admin_params_schema["unsubscribe"]),
            None
        )

    def test_client_params_schema_subscribe(self):
        schema = {
            "namespace": "channel",
            "channel": "test"
        }

        self.assertEqual(
            validate(schema, client_params_schema["subscribe"]),
            None
        )

    def test_client_params_schema_unsubscribe(self):
        schema = {
            "namespace": "channel",
            "channel": "test"
        }

        self.assertEqual(
            validate(schema, client_params_schema["unsubscribe"]),
            None
        )

    def test_client_params_schema_auth(self):
        schema = {
            "token": "test",
            "user": "test",
            "project": "test",
        }

        self.assertEqual(
            validate(schema, client_params_schema["connect"]),
            None
        )

if __name__ == '__main__':
    main()