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
            "namespace": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["channel"]
    },
    "presence": {
        "type": "object",
        "properties": {
            "namespace": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["channel"]
    },
    "history": {
        "type": "object",
        "properties": {
            "namespace": {
                "type": "string"
            },
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
            "namespace": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["user"]
    },
    "namespace_list": {
        "type": "object",
        "properties": {}
    },
    "namespace_create": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string"
            },
            "publish": {
                "type": "boolean"
            },
            "is_watching": {
                "type": "boolean"
            },
            "presence": {
                "type": "boolean"
            },
            "history": {
                "type": "boolean"
            },
            "history_size": {
                "type": "integer"
            },
            "is_private": {
                "type": "boolean"
            },
            "auth_address": {
                "type": "string"
            },
            "join_leave": {
                "type": "boolean"
            }
        },
        "required": ["name"]
    },
    "namespace_edit": {
        "type": "object",
        "properties": {
            "id": {
                "type": "string"
            },
            "name": {
                "type": "string"
            },
            "publish": {
                "type": "boolean"
            },
            "is_watching": {
                "type": "boolean"
            },
            "presence": {
                "type": "boolean"
            },
            "history": {
                "type": "boolean"
            },
            "history_size": {
                "type": "integer"
            },
            "is_private": {
                "type": "boolean"
            },
            "auth_address": {
                "type": "string"
            },
            "join_leave": {
                "type": "boolean"
            }
        },
        "required": ["id", "name"]
    },
    "namespace_delete": {
        "type": "object",
        "properties": {
            "id": {
                "type": "string"
            }
        }
    }
}

client_params_schema = {
    "publish": admin_params_schema["publish"],
    "presence": admin_params_schema["presence"],
    "history": admin_params_schema["history"],
    "subscribe": {
        "type": "object",
        "properties": {
            "namespace": {
                "type": "string"
            },
            "channel": {
                "type": "string"
            }
        },
        "required": ["channel"]
    },
    "unsubscribe": {
        "type": "object",
        "properties": {
            "namespace": {
                "type": "string"
            },
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
            }
        },
        "required": ["token", "user", "project"]
    }
}