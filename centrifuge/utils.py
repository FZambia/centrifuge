# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

from __future__ import with_statement
import sys
import six

try:
    import ujson
    json_encode = ujson.dumps
    json_decode = ujson.loads
except ImportError:
    from tornado.escape import json_encode, json_decode


if six.PY3:
    def reraise(exception, traceback):
        raise exception.with_traceback(traceback)
else:
    exec("""def reraise(exception, traceback):
    raise exception.__class__, exception, traceback""")


class _NoModuleFound(Exception):
    """
    No module was found because none exists.
    """


class InvalidName(ValueError):
    """
    The given name is not a dot-separated list of Python objects.
    """


class ModuleNotFound(InvalidName):
    """
    The module associated with the given name doesn't exist and it can't be
    imported.
    """


class ObjectNotFound(InvalidName):
    """
    The object associated with the given name doesn't exist and it can't be
    imported.
    """


def _importAndCheckStack(importName):
    """
    Import the given name as a module, then walk the stack to determine whether
    the failure was the module not existing, or some code in the module (for
    example a dependent import) failing. This can be helpful to determine
    whether any actual application code was run. For example, to distiguish
    administrative error (entering the wrong module name), from programmer
    error (writing buggy code in a module that fails to import).

    @raise Exception: if something bad happens. This can be any type of
    exception, since nobody knows what loading some arbitrary code might do.

    @raise _NoModuleFound: if no module was found.
    """
    try:
        try:
            return __import__(importName)
        except ImportError:
            excType, excValue, excTraceback = sys.exc_info()
            while excTraceback:
                execName = excTraceback.tb_frame.f_globals["__name__"]
                if execName is None or execName == importName:
                    reraise(excValue, excTraceback)
                excTraceback = excTraceback.tb_next
            raise _NoModuleFound()
    except:
        # Necessary for cleaning up modules in 2.3.
        sys.modules.pop(importName, None)
        raise


def namedAny(name):
    """
    From Twisted source code.

    Retrieve a Python object by its fully qualified name from the global Python
    module namespace. The first part of the name, that describes a module,
    will be discovered and imported. Each subsequent part of the name is
    treated as the name of an attribute of the object specified by all of the
    name which came before it. For example, the fully-qualified name of this
    object is 'twisted.python.reflect.namedAny'.

    @type name: L{str}
    @param name: The name of the object to return.

    @raise InvalidName: If the name is an empty string, starts or ends with
    a '.', or is otherwise syntactically incorrect.

    @raise ModuleNotFound: If the name is syntactically correct but the
    module it specifies cannot be imported because it does not appear to
    exist.

    @raise ObjectNotFound: If the name is syntactically correct, includes at
    least one '.', but the module it specifies cannot be imported because
    it does not appear to exist.

    @raise AttributeError: If an attribute of an object along the way cannot be
    accessed, or a module along the way is not found.

    @return: the Python object identified by 'name'.
    """
    if not name:
        raise InvalidName('Empty module name')

    names = name.split('.')

    # if the name starts or ends with a '.' or contains '..', the __import__
    # will raise an 'Empty module name' error. This will provide a better error
    # message.
    if '' in names:
        raise InvalidName(
            "name must be a string giving a '.'-separated list of Python "
            "identifiers, not %r" % (name,))

    topLevelPackage = None
    moduleNames = names[:]
    while not topLevelPackage:
        if moduleNames:
            trial_name = '.'.join(moduleNames)
            try:
                topLevelPackage = _importAndCheckStack(trial_name)
            except _NoModuleFound:
                moduleNames.pop()
        else:
            if len(names) == 1:
                raise ModuleNotFound("No module named %r" % (name,))
            else:
                raise ObjectNotFound('%r does not name an object' % (name,))

    obj = topLevelPackage
    for n in names[1:]:
        obj = getattr(obj, n)

    return obj


try:
    from importlib import import_module
except ImportError:
    def _resolve_name(name, package, level):
        """Return the absolute name of the module to be imported."""
        if not hasattr(package, 'rindex'):
            raise ValueError("'package' not set to a string")
        dot = len(package)
        for x in range(level, 1, -1):
            try:
                dot = package.rindex('.', 0, dot)
            except ValueError:
                raise ValueError("attempted relative import beyond top-level "
                                 "package")
        return "%s.%s" % (package[:dot], name)

    def import_module(name, package=None):
        """
        From Gunicorn source code.

        Import a module.
        The 'package' argument is required when performing a relative import. It
        specifies the package to use as the anchor point from which to resolve the
        relative import to an absolute import.
        """
        if name.startswith('.'):
            if not package:
                raise TypeError("relative imports require the 'package' argument")
            level = 0
            for character in name:
                if character != '.':
                    break
                level += 1
            name = _resolve_name(name[level:], package, level)
        __import__(name)
        return sys.modules[name]

