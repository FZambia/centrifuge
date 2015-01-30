# -*- coding: utf-8 -*-
import sys
import os

# If extensions (or modules to document with autodoc) are in another directory,
# add these directories to sys.path here. If the directory is relative to the
# documentation root, use os.path.abspath to make it absolute, like shown here.
sys.path.append(os.path.abspath('_themes'))

# Add any Sphinx extension module names here, as strings. They can be extensions
# coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinx.ext.ifconfig',
    'sphinx.ext.todo',
    'sphinx.ext.intersphinx',
    'sphinx.ext.doctest',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'centrifuge'

copyright = u'2015, <a href="https://www.facebook.com/emelin.alexander">Alexandr Emelin</a>'

# The short X.Y version.
version = '0.6.3'
# The full version, including alpha/beta/rc tags.
release = '0.6.3'

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'flask_theme_support.FlaskyStyle'

# -- Options for HTML output ---------------------------------------------------

# The theme to use for HTML and HTML Help pages.  See the documentation for
# a list of builtin themes.
html_theme = 'kr'

# Add any paths that contain custom themes here, relative to this directory.
html_theme_path = ['_themes']

# The name for this set of Sphinx documents.  If None, it defaults to
# "<project> v<release> documentation".
html_title = 'Centrifuge'

html_static_path = ['_static']

html_sidebars = {
    'index':    ['sidebarintro.html', 'sourcelink.html', 'searchbox.html'],
    '**':       ['sidebarlogo.html', 'localtoc.html', 'relations.html',
                 'sourcelink.html', 'searchbox.html']
}

html_show_sourcelink = True

# If true, "Created using Sphinx" is shown in the HTML footer. Default is True.
html_show_sphinx = False

htmlhelp_basename = 'centrifugedocs'

epub_title = u'centrifuge'
epub_author = u'Alexandr Emelin'
epub_publisher = u'Alexandr Emelin'
epub_copyright = u'2015, Alexandr Emelin'

todo_include_todos = True

intersphinx_mapping = {
    'python': ('http://docs.python.org/', None),
}
