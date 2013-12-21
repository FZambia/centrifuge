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

owner_api_methods = [
    "project_list", "project_create", "dump_structure"
]

server_api_schema = {
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
    "namespace_by_name": {
        "type": "object",
        "properties": {
            "_id": {
                "type": "string"
            },
            "name": {
                "type": "string"
            }
        },
        "required": ["name"]
    },
    "namespace_get": {
        "type": "object",
        "properties": {
            "_id": {
                "type": "string"
            }
        },
        "required": ["_id"]
    },
    "namespace_create": {
        "type": "object",
        "properties": {}
    },
    "namespace_edit": {
        "type": "object",
        "properties": {
            "_id": {
                "type": "string"
            }
        },
        "required": ["_id"]
    },
    "namespace_delete": {
        "type": "object",
        "properties": {
            "_id": {
                "type": "string"
            }
        },
        "required": ["_id"]
    },
    "project_list": {
        "type": "object",
        "properties": {}
    },
    "project_get": {
        "type": "object",
        "properties": {
            "_id": {
                "type": "string"
            }
        }
    },
    "project_by_name": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string"
            }
        },
        "required": ["name"]
    },
    "project_create": {
        "type": "object",
        "properties": {}
    },
    "project_edit": {
        "type": "object",
        "properties": {
            "_id": {
                "type": "string"
            }
        }
    },
    "project_delete": {
        "type": "object",
        "properties": {
            "_id": {
                "type": "string"
            }
        }
    },
    "regenerate_secret_key": {
        "type": "object",
        "properties": {}
    },
    "dump_structure": {
        "type": "object",
        "properties": {}
    }
}

client_api_schema = {
    "publish": server_api_schema["publish"],
    "presence": server_api_schema["presence"],
    "history": server_api_schema["history"],
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
            },
            "info": {
                "type": "string"
            }
        },
        "required": ["token", "user", "project"]
    }
}
