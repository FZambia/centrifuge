# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

from copy import deepcopy
from jsonschema import validate, ValidationError
from centrifuge.schema import project_schema, namespace_schema


def structure_to_dict(structure):
    """
    Transform provided and already validated structure to dictionary
    to speed up lookups
    """
    to_return = {}
    for project in deepcopy(structure):
        new_namespaces = {}
        namespaces = project.get("namespaces", [])[:]
        for namespace in namespaces:
            new_namespaces[namespace["name"]] = namespace
        project["namespaces"] = new_namespaces
        to_return[project["name"]] = project
    return to_return


def validate_structure(structure):
    """
    Validate structure configuration
    """
    if not structure:
        raise ValidationError(
            "Since Centrifuge 0.8.0 structure must be set in configuration file"
        )

    if not isinstance(structure, list):
        raise ValidationError("structure must be array of projects")

    project_names = []
    project_names_append = project_names.append

    for project in structure:

        validate(project, project_schema)

        namespace_names = []
        namespace_names_append = namespace_names.append

        name = project["name"]
        if name in project_names:
            raise ValidationError("project name must be unique")
        project_names_append(name)

        if "namespaces" not in project:
            continue

        namespaces = project["namespaces"]
        if not isinstance(namespaces, list):
            raise ValidationError("namespaces must be array of namespaces")

        for namespace in namespaces:

            validate(namespace, namespace_schema)

            name = namespace["name"]
            if name in namespace_names:
                raise ValidationError("namespace name must be unique for project")
            namespace_names_append(name)
