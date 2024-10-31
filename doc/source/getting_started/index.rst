.. _ref_getting_started:

Getting started
###############

.. _ref_software_requirements:

Software requirements
~~~~~~~~~~~~~~~~~~~~~~
.. include:: ../../../README.rst
      :start-after: readme_software_requirements
      :end-before: readme_software_requirements_end


Installation
~~~~~~~~~~~~
.. include:: ../../../README.rst
      :start-after: readme_installation
      :end-before: readme_installation_end


Brief example
~~~~~~~~~~~~~
This brief example demonstrates how the client works:

.. code:: python

    >>> from ansys.openapi.common import ApiClientFactory
    >>> client = ApiClientFactory("https://my-api.com")
    ...          .with_autologon()
    ...          .connect()
    >>> print(client)

    <ApiClient url: http://my-api.com>


The client is now ready and available for use with an OpenAPI client.
