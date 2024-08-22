.. _contributing_openapi:

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
:class:`~ansys.openapi.common.ApiClientFactory` is typically subclassed, and the builder
methods are shown within the sub-classing package's documentation as part of **that**
module's subclass.

One common example of where this is important is in ``.. versionadded::`` directives.
To document that a certain feature was added in version 2.1 of ``ansys.openapi.common``,
always use the following approach:

.. code-block:: restructuredtext

   .. only:: openapi-common-standalone

       .. versionadded:: 2.1

   .. only:: not openapi-common-standalone

       .. tip::
          Added to :doc:`ansys-openapi-common <openapi-common:index>` in version 2.1.


The ``openapi-common-standalone`` tag is added automatically during the documentation
build process, which ensures that:

* When building the documentation for this package, the ``.. versionadded::``
  directive is used.
* When building the documentation for a package that inherits from this package,
  the more generic ``.. tip::`` directive is used, and additional context about
  the change is provided.

.. note::

   The example code includes a link to the documentation for this package via
   :doc:`Intersphinx <sphinx:usage/extensions/intersphinx>`. The Intersphinx
   mapping for this package should always be set to ``openapi-common`` to
   ensure the links included in this package are generated correctly.
