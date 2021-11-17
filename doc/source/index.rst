Common Authentication Components Documentation
==============================================

.. toctree::
   :hidden:
   :maxdepth: 3

   api/api.rst
   contributing.rst


Introduction and Purpose
------------------------
This project is part of the larger PyAnsys effort to facilitate the use
of Ansys technologies directly from within Python.

Some Ansys products expose HTTP APIs rather than the more common gRPC,
this package is designed to provide a common client to consume these
APIs, minimizing overhead and reducing code duplication.


Background
----------
A widely used standard for HTTP REST-style APIs is the OpenAPI standard,
formerly known as Swagger. This client is designed to be used alongside
code generation tools to produce client libraries for these APIs.


Quick Code
----------
Here's a brief example of how the client works:

.. code:: python

    >>> from ansys.grantami.common import ApiClientFactory
    >>> client = ApiClientFactory("https://my-api.com").with_autologon().build()
    >>> print(client)

    <ApiClient url: http://my-api.com>

The client is now ready and available for use with an OpenAPI client.

Different API servers will have different authentication requirements, the library currently
supports:

- Anonymous (no authentication)
- Basic
- NTLM with credentials
- Negotiate
- OpenID Connect (With Granta MI only)

Advanced Features
-----------------
All options that are available in the python library *requests* can be set through
the client, this enables you to configure custom SSL certificate validation, send
client certificates if your API server requires them, and many other options.

For example to send a client certificate with every request

.. code:: python

   >>> from ansys.grantami.common import SessionConfiguration
   >>> configuration = SessionConfiguration(client_cert_path='./my-client-cert.pwm', client_cert_key='secret-key')
   >>> client.configuration = configuration

API Reference
-------------
For full details of the API available see the :doc:`API reference <api/api>`.

Contributing
------------
Contributions to this repository are welcomed, please see the :doc:`Contributor Guide<contributing>`
for more information.

Project Index
-------------

* :ref:`genindex`
