# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
from __future__ import with_statement

import sys
from lxml.html import clean


if sys.version_info < (3, 0):
    _PY3 = False
else:
    _PY3 = True


if _PY3:
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
            trialname = '.'.join(moduleNames)
            try:
                topLevelPackage = _importAndCheckStack(trialname)
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


class Bleacher(clean.Cleaner):

    safe_attrs_only = True

    safe_attrs = frozenset([
        'abbr', 'accept', 'accept-charset', 'accesskey', 'action', 'align',
        'alt', 'axis', 'border', 'cellpadding', 'cellspacing', 'char', 'charoff',
        'charset', 'checked', 'cite', 'class', 'clear', 'cols', 'colspan',
        'color', 'compact', 'coords', 'datetime', 'dir', 'disabled', 'enctype',
        'for', 'frame', 'headers', 'height', 'href', 'hreflang', 'hspace',
        'ismap', 'label', 'lang', 'longdesc', 'maxlength', 'media', 'method',
        'multiple', 'name', 'nohref', 'noshade', 'nowrap', 'prompt', 'readonly',
        'rel', 'rev', 'rows', 'rowspan', 'rules', 'scope', 'selected', 'shape',
        'size', 'span', 'src', 'start', 'summary', 'tabindex', 'target', 'title',
        'type', 'usemap', 'valign', 'value', 'vspace', 'width'
    ])

    _tag_link_attrs = dict(
        iframe='src',
        embed='src',
        a='href'
    )


def clean_html(html, host_whitelist=()):
    cleaner = Bleacher(host_whitelist=host_whitelist)
    cleaned_html = cleaner.clean_html('<body>' + html + '</body>')
    linkified_html = clean.autolink_html(cleaned_html)
    return linkified_html


# from https://github.com/benoitc/gunicorn/blob/master/gunicorn/util.py
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
        """Import a module.
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
