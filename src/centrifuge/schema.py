# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#


req_schema = {
    "type": "object",
    "properties": {
        "id": {
            "type": "string"
        },
        "method": {
            "type": "string"
        },
        "params": {
            "type": "object"
        }
    },
    "required": ["method", "params"]
}

admin_params_schema = {
    "broadcast": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            },
            "data": {
                "type": "object"
            },
            "unique_keys": {
                "type": "array"
            }
        },
        "required": ["category", "channel", "data"]
    },
    "subscribe": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string"
            },
            "to": {
                "type": "object"
            }
        },
        "required": ["user", "to"]
    },
    "unsubscribe": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string"
            },
            "from": {
                "type": "object"
            }
        },
        "required": ["user", "from"]
    }
}

client_params_schema = {
    "broadcast": admin_params_schema["broadcast"],
    "subscribe": {
        "type": "object",
        "properties": {
            "to": {
                "type": "object"
            }
        },
        "required": ["to"]
    },
    "unsubscribe": {
        "type": "object",
        "properties": {
            "from": {
                "type": "object"
            }
        },
        "required": ["from"]
    },
    "auth": {
        "type": "object",
        "properties": {
            "token": {
                "type": "string",
            },
            "user": {
                "type": "string"
            },
            "project_id": {
                "type": "string"
            },
            "permissions": {
                "type": "object",
            }
        },
        "required": ["token", "user", "project_id", "permissions"]
    }
}