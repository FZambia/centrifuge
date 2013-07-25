# coding: utf-8
#
# Copyright (c) Alexandr Emelin. BSD license.
# All rights reserved.
#
from __future__ import with_statement

import sys
from lxml.html import clean


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
