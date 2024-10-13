from __future__ import annotations

import datetime

# sys.path.insert(0, os.path.abspath("../src"))
from MeasurementSystem.version import __version__

##########################
# Project information
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information
#

project = "Measurement System"
author = "Alfred Paar"
copyright = f"{datetime.datetime.now(tz=datetime.timezone.utc).year}, Alfred Paar"

version = release = __version__

##########################
# General configuration
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration
#

master_doc = "index"
templates_path = ["_templates"]
exclude_patterns = ["build_docs"]

extensions = [
    "sphinx_rtd_theme",  #
    "sphinx.ext.autodoc",  #
    "sphinx.ext.autosectionlabel",
    "sphinx.ext.viewcode",
    "sphinx.ext.todo",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "rst2pdf.pdfbuilder",
    "myst_parser",
]

# mocking imports for a leigtweight build
autodoc_mock_imports = []

# Optionally, you can also set the following options to customize the behavior
autodoc_default_options = {
    "members": True,
    "members-order": "bysource",
    "special-members": False,
    "private-members": False,
    "undoc-members": False,
    "inherited-members": False,  # members of base class
    "show-inheritance": True,
    "exclude-members": "__dict__, __weakref__",
}

autoclass_content = "class"

autodoc_preserve_defaults = True

add_function_parentheses = True
add_module_names = False
toc_object_entries_show_parents = "hide"
pygments_style = "default"


########################
# PDF

# pdf_documents = [("index", "YourProjectName", "Your Project Documentation", "Author Name")]

# pdf_stylesheets = ["sphinx", "custom"]

# pdf_style_path = ["_static"]  # Location of your stylesheet
# pdf_stylesheets = ["custom-rtd-pdf.style"]  # Your custom style
pdf_compressed = True  # Compress PDF output
# pdf_fit_mode = "shrink"  # Shrink pages to fit


########################
# HTML
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output
#

html_theme = "sphinx_rtd_theme"
html_static_path = ["_static"]
html_logo = "_static/logo.png"
# html_favicon = "_static/favicon.ico"
# html_style = "sphinx_rtd_theme_overrides.css"

html_theme_options = {
    "logo_only": True,
    "display_version": True,  # depreciated since version 3.0.0, workaround to be found, until now fix version <3
    "prev_next_buttons_location": "bottom",
    "style_external_links": False,
    "vcs_pageview_mode": "",
    "style_nav_header_background": "#2980b9",
    # Toc options
    "collapse_navigation": False,
    "sticky_navigation": True,
    "navigation_depth": 4,
    "includehidden": True,
}

html_use_smartypants = True
html_short_title = f"{project} - {version}"


########################
# Autosectionlabel
# https://www.sphinx-doc.org/en/master/usage/extensions/autosectionlabel.html
#

autoselectionlabel_prefix_document = False
autoselectionlabel_maxdepth = None

suppress_warnings = ["autosectionlabel.changelog", "duplicate_label", "myst"]


########################
# MyST
# https://myst-parser.readthedocs.io
#

myst_enable_extensions = [
    "colon_fence",
    "attrs_inline",
]

source_suffix = {
    ".rst": "restructuredtext",
    ".txt": "markdown",
    ".md": "markdown",
}


########################
# Todo
# https://www.sphinx-doc.org/en/master/usage/extensions/todo.html
#

# If this is True, todo and todoList produce output, else they produce nothing. The default is False.
todo_include_todos = True
