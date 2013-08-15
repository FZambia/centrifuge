# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.


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
    "publish": {
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
    "presence": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["category", "channel"]
    },
    "history": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["category", "channel"]
    },
    "subscribe": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string"
            },
            "category": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["user", "category", "channel"]
    },
    "unsubscribe": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string"
            },
            "category": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["user", "category", "channel"]
    }
}

client_params_schema = {
    "publish": admin_params_schema["publish"],
    "presence": admin_params_schema["presence"],
    "history": admin_params_schema["history"],
    "subscribe": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["category", "channel"]
    },
    "unsubscribe": {
        "type": "object",
        "properties": {
            "category": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["category", "channel"]
    },
    "connect": {
        "type": "object",
        "properties": {
            "token": {
                "type": "string",
            },
            "user": {
                "type": "string"
            },
            "project": {
                "type": "string"
            }
        },
        "required": ["token", "user", "project"]
    }
}