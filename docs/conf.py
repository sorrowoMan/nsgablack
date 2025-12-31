# Configuration file for the Sphinx documentation builder.

import os
import sys
import datetime

# -- Path setup --------------------------------------------------------------
sys.path.insert(0, os.path.abspath('..'))

# -- Project information -----------------------------------------------------
project = 'nsgablack'
copyright = f'{datetime.datetime.now().year}, SorrowoMan'
author = 'SorrowoMan'
version = '2.1.0'
release = '2.1.0'

# -- General configuration ---------------------------------------------------
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.autosummary',
    'sphinx.ext.viewcode',
    'sphinx.ext.napoleon',
    'sphinx.ext.intersphinx',
    'sphinx.ext.coverage',
    'sphinx.ext.doctest',
    'sphinx.ext.mathjax',
    'sphinx_rtd_theme',
    'myst_parser',
]

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = [
    '_build',
    'Thumbs.db',
    '.DS_Store',
    '**.ipynb_checkpoints',
]

# The suffix(es) of source filenames.
source_suffix = {
    '.rst': None,
    '.md': 'myst_parser',
}

# The master toctree document.
master_doc = 'index'

# -- Options for HTML output -------------------------------------------------
html_theme = 'sphinx_rtd_theme'
html_static_path = ['_static']
html_css_files = [
    'css/custom.css',
]

# Theme options
html_theme_options = {
    'canonical_url': '',
    'analytics_id': '',
    'logo_only': False,
    'display_version': True,
    'prev_next_buttons_location': 'bottom',
    'style_external_links': False,
    'collapse_navigation': True,
    'sticky_navigation': True,
    'navigation_depth': 4,
    'includehidden': True,
    'titles_only': False
}

# Custom sidebar templates
html_sidebars = {
    '**': [
        'relations.html',
        'searchbox.html',
        'localtoc.html',
    ]
}

# -- Options for autodoc ----------------------------------------------------
autodoc_default_options = {
    'members': True,
    'member-order': 'bysource',
    'special-members': '__init__',
    'undoc-members': True,
    'exclude-members': '_weakref_'
}

autodoc_typehints = 'description'
autodoc_typehints_description_target = 'documented'

# -- Options for Napoleon (Google/NumPy style docstrings) -----------------
napoleon_google_docstring = True
napoleon_numpy_docstring = True
napoleon_include_init_with_doc = False
napoleon_include_private_with_doc = False
napoleon_include_special_with_doc = True
napoleon_use_admonition_for_examples = False
napoleon_use_admonition_for_notes = False
napoleon_use_admonition_for_references = False
napoleon_use_ivar = False
napoleon_use_param = True
napoleon_use_rtype = True
napoleon_preprocess_types = False
napoleon_type_aliases = None
napoleon_attr_annotations = True

# -- Options for intersphinx extension ---------------------------------------
# Example configuration for intersphinx: refer to the Python standard library.
intersphinx_mapping = {
    'python': ('https://docs.python.org/3/', None),
    'numpy': ('https://numpy.org/doc/stable/', None),
    'scipy': ('https://docs.scipy.org/doc/scipy/', None),
    'sklearn': ('https://scikit-learn.org/stable/', None),
    'matplotlib': ('https://matplotlib.org/stable/', None),
    'pandas': ('https://pandas.pydata.org/pandas-docs/stable/', None),
}

# -- Options for MyST parser ---------------------------------------------
myst_enable_extensions = [
    "colon_fence",
    "deflist",
    "html_admonition",
    "linkify",
    "replacements",
    "smartquotes",
    "substitution",
    "tasklist",
]

# -- Options for LaTeX output ---------------------------------------------
latex_elements = {
    'papersize': 'letterpaper',
    'pointsize': '10pt',
    'preamble': r'''
\usepackage{hyperref}
\usepackage{amsmath}
\usepackage{amssymb}
''',
}

latex_documents = [
    (master_doc, 'nsgablack.tex', 'nsgablack Documentation',
     'SorrowoMan', 'manual'),
]

# -- Options for linkcheck builder -------------------------------------------
linkcheck_ignore = [
    r'https://github.com/.*',  # GitHub links can be unreliable
    r'http://localhost.*',    # Local links
]

# -- Options for coverage extension --------------------------------------
coverage_show_missing_items = True
coverage_write_headline = True
coverage_source = [ '..', 'nsgablack']

# Custom CSS
def setup(app):
    app.add_css_file('css/custom.css')