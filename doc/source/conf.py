from datetime import datetime
import os
import sys

from ansys_sphinx_theme import get_version_match, pyansys_logo_black

from ansys.openapi import common

# -- Project information -----------------------------------------------------

project = "ansys.openapi.common"
project_copyright = f"(c) {datetime.now().year} ANSYS, Inc. All rights reserved"
author = "ANSYS Inc."
html_title = f"OpenAPI Common {common.__version__}"

sys.path.insert(0, os.path.abspath("../src"))

# The short X.Y version
release = version = common.__version__

# -- General configuration ---------------------------------------------------
extensions = [
    "sphinx.ext.autodoc",
    "numpydoc",
    "sphinx.ext.doctest",
    "sphinx.ext.autosummary",
    "notfound.extension",
    "sphinx.ext.intersphinx",
    "sphinx_copybutton",
    "sphinx.ext.extlinks",
    "sphinx.ext.coverage",
]

# Sphinx
add_module_names = False

# sphinx.ext.autodoc
autodoc_typehints = "description"
autodoc_typehints_description_target = "documented"

# sphinx.ext.intersphinx
intersphinx_mapping = {
    "python": ("https://docs.python.org/3.11", None),
    "requests": ("https://requests.readthedocs.io/en/latest", None),
}

# numpydoc configuration
numpydoc_show_class_members = False
numpydoc_xref_param_type = True

numpydoc_xref_aliases = {
    "Union": ":py:obj:`~typing.Union`",
    "Tuple": ":py:obj:`~typing.Tuple`",
    "Dict": ":py:obj:`~typing.Dict`",
    "List": ":py:obj:`~typing.List`",
}
numpydoc_validation_exclude = {
    "ansys.openapi.common._base.DeserializedType",
    "ansys.openapi.common._base.SerializedType",
    "ansys.openapi.common._base.PrimitiveType",
}
# Consider enabling numpydoc validation. See:
# https://numpydoc.readthedocs.io/en/latest/validation.html#
numpydoc_validate = True
numpydoc_validation_checks = {
    "GL06",  # Found unknown section
    "GL07",  # Sections are in the wrong order.
    "GL08",  # The object does not have a docstring
    "GL09",  # Deprecation warning should precede extended summary
    "GL10",  # reST directives {directives} must be followed by two colons
    "SS01",  # No summary found
    "SS02",  # Summary does not start with a capital letter
    # "SS03", # Summary does not end with a period
    "SS04",  # Summary contains heading whitespaces
    # "SS05", # Summary must start with infinitive verb, not third person
    "RT02",  # The first line of the Returns section should contain only the
    # type, unless multiple values are being returned"
}

# static path
html_static_path = ["_static"]

# Add any paths that contain templates here, relative to this directory.
templates_path = ["_templates"]

# The suffix(es) of source filenames.
source_suffix = ".rst"

# The master toctree document.
master_doc = "index"

# The language for content autogenerated by Sphinx. Refer to documentation
# for a list of supported languages.
#
# This is also used if you do content translation via gettext catalogs.
# Usually you set "language" from the command line for these cases.
language = "en"

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
# This pattern also affects html_static_path and html_extra_path.
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = "sphinx"

# If true, `todo` and `todoList` produce output, else they produce nothing.
todo_include_todos = False

# Copy button customization ---------------------------------------------------
# exclude traditional Python prompts from the copied code
copybutton_prompt_text = r">>> ?|\.\.\. "
copybutton_prompt_is_regexp = True


# -- Options for HTML output -------------------------------------------------
cname = os.getenv("DOCUMENTATION_CNAME", "ansys.github.io/openapi-common/")

html_theme = "ansys_sphinx_theme"
html_logo = pyansys_logo_black
html_theme_options = {
    "github_url": "https://github.com/pyansys/openapi-common",
    "show_prev_next": False,
    "show_breadcrumbs": True,
    "additional_breadcrumbs": [
        ("PyAnsys Documentation", "https://docs.pyansys.com"),
        ("Shared Components", "https://shared.docs.pyansys.com"),
    ],
    "switcher": {
        "json_url": f"https://{cname}/versions.json",
        "version_match": get_version_match(common.__version__),
    },
    "check_switcher": False,
}

# -- Options for HTMLHelp output ---------------------------------------------

# Output file base name for HTML help builder.
htmlhelp_basename = "openapicommondoc"
