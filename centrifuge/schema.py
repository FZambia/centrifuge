# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

req_schema = {
    "type": "object",
    "properties": {
        "method": {
            "type": "string"
        },
        "params": {
            "type": "object"
        }
    },
    "required": ["method", "params"]
}

server_api_schema = {
    "publish": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string"
            }
        },
        "required": ["channel"]
    },
    "presence": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string"
            }
        },
        "required": ["channel"]
    },
    "history": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string"
            }
        },
        "required": ["channel"]
    },
    "unsubscribe": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["user"]
    },
    "disconnect": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string"
            },
            "reason": {
                "type": "string"
            }
        },
        "required": ["user"]
    }
}

client_api_schema = {
    "publish": server_api_schema["publish"],
    "presence": server_api_schema["presence"],
    "history": server_api_schema["history"],
    "ping": {
        "type": "object"
    },
    "subscribe": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string"
            },
            "client": {
                "type": "string"
            },
            "info": {
                "type": "string"
            },
            "sign": {
                "type": "string"
            },
        },
        "required": ["channel"]
    },
    "unsubscribe": {
        "type": "object",
        "properties": {
            "channel": {
                "type": "string"
            }
        },
        "required": ["channel"]
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
            },
            "timestamp": {
                "type": "string"
            },
            "info": {
                "type": "string"
            }
        },
        "required": ["token", "user", "project", "timestamp"]
    },
    "connect_insecure": {
        "type": "object",
        "properties": {
            "user": {
                "type": "string"
            },
            "project": {
                "type": "string"
            },
            "info": {
                "type": "string"
            }
        },
        "required": ["user", "project"]
    },
    "refresh": {
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
            },
            "timestamp": {
                "type": "string"
            },
            "info": {
                "type": "string"
            }
        },
        "required": ["token", "user", "project", "timestamp"]
    }
}
