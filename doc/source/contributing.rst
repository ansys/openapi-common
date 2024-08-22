.. _contributing_openapi:

.. currentmodule:: ansys.openapi.common

==========
Contribute
==========
Overall guidance on contributing to a PyAnsys library appears in the
`Contributing <https://dev.docs.pyansys.com/overview/contributing.html>`_ topic
in the *PyAnsys Developer's Guide*. Ensure that you are thoroughly familiar
with this guide before attempting to contribute to OpenAPI-Common.

The following contribution information is specific to OpenAPI-Common.

Clone the repository
--------------------

To clone and install the latest version of OpenAPI-Common in *development* mode,
run:

.. code::

    git clone https://github.com/pyansys/openapi-common
    cd openapi-common
    pip install .


Post issues
-----------

Use the `OpenAPI-Common Issues <https://github.com/pyansys/openapi-common/issues>`_ page
to submit questions, report bugs, and request new features.

To reach the support team, email `pyansys.support@ansys.com <pyansys.support@ansys.com>`_.


Documentation conventions
-------------------------

When contributing to this package, always consider that many docstrings are viewed within
the context of a package that inherits from classes defined in this package. For example,
:class:`~.ApiClientFactory` is typically subclassed, and the builder methods are shown
within the subclassing package's documentation as part of **that** module's subclass.
The advice in this section ensures that a subclassing package can build documentation
that inherits docstrings from this package.

Docstring type references
~~~~~~~~~~~~~~~~~~~~~~~~~

In cases where a class is intended to be subclassed, internal type references should be
fully qualified. For example, instead of::

    Parameters
    ----------
    authentication_scheme : AuthenticationScheme
        The authentication scheme to use.

use::

    Parameters
    ----------
    authentication_scheme : ~ansys.openapi.common.AuthenticationScheme
        The authentication scheme to use.

This ensures that other packages that inherit from this package are able to resolve
these types via :doc:`Intersphinx <sphinx:usage/extensions/intersphinx>`.

References to this package
~~~~~~~~~~~~~~~~~~~~~~~~~~

Docstrings often contain implicit and explicit references to the package they are
documenting. One common example of an implicit reference is in
``.. versionadded::`` directives, where the directive implicitly refers to a version
of the package being documented. To make these references explicit when they occur
outside of this package, always use the following approach:

.. code-block:: restructuredtext

   .. only:: OpenapiCommonStandaloneBuild

       .. versionadded:: 2.1

   .. only:: OpenapiCommonStandaloneBuild

       .. tip::
          Added to :class:`~ansys.openapi.common.ClassName` in version 2.1 of
          ``ansys-openapi-common``.

Where ``:class:`ansys.openapi.common.ClassName``` is a reference to the relevant
entity that contains the change. This approach ensures that:

* When building the documentation for this package, the ``.. versionadded::``
  directive is used and *implicitly* refers to version 2.1 of this package.
* When building the documentation for a package that inherits from classes
  defined in this package, the more generic ``.. tip::`` directive is used,
  and *explicitly* refers to version 2.1 of this package.

.. note::

   If the inheriting package has configured
   :doc:`Intersphinx <sphinx:usage/extensions/intersphinx>`, then Sphinx
   automatically adds a cross-reference to the relevant location in the API
   documentation for this package.
