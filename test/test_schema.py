# coding: utf-8
from unittest import TestCase, main


from centrifuge.schema import req_schema, server_api_schema, client_api_schema
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

        schema["method"] = 1
        try:
            validate(schema, req_schema)
        except ValidationError:
            pass
        else:
            self.assertTrue(False)

    def test_server_api_schema_publish(self):
        schema = {
            "namespace": "test",
            "channel": "test",
            "data": {"input": "test"}
        }

        self.assertEqual(
            validate(schema, server_api_schema["publish"]),
            None
        )

        del schema["namespace"]

        self.assertEqual(
            validate(schema, server_api_schema["publish"]),
            None
        )

    def test_server_api_schema_unsubscribe(self):
        schema = {
            "user": "test",
            "namespace": "channel",
            "channel": "test"
        }

        self.assertEqual(
            validate(schema, server_api_schema["unsubscribe"]),
            None
        )

    def test_client_api_schema_subscribe(self):
        schema = {
            "namespace": "channel",
            "channel": "test"
        }

        self.assertEqual(
            validate(schema, client_api_schema["subscribe"]),
            None
        )

    def test_client_api_schema_unsubscribe(self):
        schema = {
            "namespace": "channel",
            "channel": "test"
        }

        self.assertEqual(
            validate(schema, client_api_schema["unsubscribe"]),
            None
        )

    def test_client_api_schema_connect(self):
        schema = {
            "token": "test",
            "user": "test",
            "project": "test",
            "timestamp": "123"
        }

        self.assertEqual(
            validate(schema, client_api_schema["connect"]),
            None
        )

        schema = {
            "token": "test",
            "user": "test",
            "project": "test",
            "timestamp": "123",
            "info": 1
        }
        try:
            validate(schema, client_api_schema["connect"])
        except ValidationError:
            pass
        else:
            raise AssertionError("Exception must be raised here")

        schema = {
            "token": "test",
            "user": "test",
            "project": "test",
            "timestamp": "123",
            "info": "{}"
        }

        self.assertEqual(
            validate(schema, client_api_schema["connect"]),
            None
        )


if __name__ == '__main__':
    main()
