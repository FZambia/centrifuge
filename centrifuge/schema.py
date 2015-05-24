# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

_channel_options_properties = {
    "watch": {
        "type": "boolean"
    },
    "publish": {
        "type": "boolean"
    },
    "anonymous": {
        "type": "boolean"
    },
    "presence": {
        "type": "boolean"
    },
    "join_leave": {
        "type": "boolean"
    },
    "history_size": {
        "type": "integer",
        "minimum": 0
    },
    "history_lifetime": {
        "type": "integer",
        "minimum": 0
    }
}

_project_properties = {
    "name": {
        "type": "string",
        "pattern": r'^[-a-zA-Z0-9_]{2,}$'
    },
    "secret": {
        "type": "string"
    },
    "connection_lifetime": {
        "type": "integer",
        "minimum": 0
    },
    "namespaces": {
        "type": "array"
    }
}

_project_properties.update(_channel_options_properties)

_namespace_properties = {
    "name": {
        "type": "string"
    }
}

_namespace_properties.update(_channel_options_properties)

project_schema = {
    "type": "object",
    "properties": _project_properties,
    "required": ["name", "secret"]
}

namespace_schema = {
    "type": "object",
    "properties": _namespace_properties,
    "required": ["name"]
}

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
