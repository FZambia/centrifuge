# -*- coding: utf-8 -*-
import sys
import os
sys.path.insert(0, os.path.abspath(".."))
import centrifuge

master_doc = "index"
project = "Centrifuge"
copyright = u'2015, Alexandr Emelin'
version = release = centrifuge.__version__

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.coverage",
    "sphinx.ext.extlinks",
    "sphinx.ext.intersphinx",
    "sphinx.ext.viewcode",
]

html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = False

intersphinx_mapping = {
    'python': ('http://python.readthedocs.org/en/latest/', None),
}

html_theme = "sphinx_rtd_theme"
html_theme_path = ["_themes", ]

