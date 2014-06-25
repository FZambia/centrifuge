# coding: utf-8
# Copyright (c) Alexandr Emelin. MIT license.

from __future__ import with_statement
import sys
import six
import weakref
from wtforms import Form as WTForm

try:
    import ujson
    json_encode = ujson.dumps
    json_decode = ujson.loads
except ImportError:
    from tornado.escape import json_encode, json_decode


class Form(WTForm):
    """
    WTForms wrapper for Tornado.
    """

    def __init__(self, formdata=None, obj=None, prefix='', **kwargs):
        super(Form, self).__init__(
            MultiDictWrapper(formdata), obj=obj, prefix=prefix, **kwargs
        )

    def __iter__(self):
        field_order = getattr(self, 'field_order', None)
        if field_order:
            temp_fields = []
            for name in field_order:
                if name == '*':
                    temp_fields.extend([f for f in self._unbound_fields if f[0] not in field_order])
                else:
                    temp_fields.append([f for f in self._unbound_fields if f[0] == name][0])
            self._unbound_fields = temp_fields
        return super(Form, self).__iter__()


class MultiDictWrapper(object):
    """
    Wrapper class to provide form values to wtforms.Form

    This class is tightly coupled to a request handler, and more importantly
    one of our BaseHandlers which has a 'context'. At least if you want to use
    the save/load functionality.

    Some of this more difficult that it otherwise seems like it should be because of nature
    of how tornado handles it's form input.
    """
    def __init__(self, handler):
        # We keep a weakref to prevent circular references
        # This object is tightly coupled to the handler...
        # which certainly isn't nice, but it's the
        # way it's gonna have to be for now.
        if handler and isinstance(handler, dict):
            self.handler = handler
        elif handler:
            self.handler = weakref.ref(handler)
        else:
            self.handler = None

    @property
    def _arguments(self):
        if not self.handler:
            return {}
        if isinstance(self.handler, dict):
            to_return = {}
            for key, value in six.iteritems(self.handler):
                to_return.setdefault(key, []).append(value)
            return to_return
        return self.handler().request.arguments

    def __iter__(self):
        return iter(self._arguments)

    def __len__(self):
        return len(self._arguments)

    def __contains__(self, name):
        # We use request.arguments because get_arguments always returns a
        # value regardless of the existence of the key.
        return name in self._arguments

    def getlist(self, name):
        # get_arguments by default strips whitespace from the input data,
        # so we pass strip=False to stop that in case we need to validate
        # on whitespace.
        if isinstance(self.handler, dict):
            return self._arguments.get(name, [])
        return self.handler().get_arguments(name, strip=False)

    def __getitem__(self, name):
        if isinstance(self.handler, dict):
            return self.handler.get(name)
        return self.handler().get_argument(name)


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


def make_patch_data(form, params):
    """
    Return a dictionary with keys which present in request params and in form data
    """
    data = form.data.copy()
    keys_to_delete = list(set(data.keys()) - set(params.keys()))
    for key in keys_to_delete:
        del data[key]
    return data


def get_boolean_patch_data(boolean_fields, params):
    """
    Used as work around HTML form behaviour for checkbox (boolean) fields - when
    boolean field must be set as False then it must not be in request params.
    Here we construct dictionary with keys which present in request params and must
    be interpreted as False. This is necessary as Centrifuge uses partial updates in API.
    """
    boolean_patch_data = {}
    for field in boolean_fields:
        if field in params and not bool(params[field]):
            boolean_patch_data[field] = False
    return boolean_patch_data
