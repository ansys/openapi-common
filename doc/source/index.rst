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

    >>> from ansys.openapi.common import ApiClientFactory
    >>> client = ApiClientFactory("https://my-api.com")
    ...          .with_autologon()
    ...          .connect()
    >>> print(client)

    <ApiClient url: http://my-api.com>

The client is now ready and available for use with an OpenAPI client.

Supported Authentication Schemes
--------------------------------
The core library supports API servers configured with no authentication, API Key, Client Certificates and Basic
authentication. Windows users can also use Windows Integrated Authentication to connect to Kerberos enabled APIs with
their windows credentials, and NTLM where it is supported.

Linux users can make use of Kerberos authentication via the ``[linux-kerberos]`` extra, this will require a working
installation of either MIT Kerberos or Heimdal, as well as some platform specific build steps. It will also require a
correctly configured ``krb5.keytab`` file on your system.

Windows and Linux users can authenticate with OIDC enabled APIs by using the ``[oidc]`` extra, currently we support only
the Authorization Code authentication flow.

.. list-table:: Authentication Methods by Platform
   :header-rows: 1

   * - Authentication Method
     - Windows
     - Linux
   * - API Key
     - ✔️
     - ✔️
   * - Client Certificate
     - ✔️
     - ✔️
   * - Basic
     - ✔️
     - ✔️
   * - NTLM
     - ✔️
     - ❌
   * - Kerberos
     - ✔️
     - ➕ with ``[linux-kerberos]`` extra
   * - OIDC
     - ➕ with ``[oidc]`` extra
     - ➕ with ``[oidc]``` extra

Advanced Features
-----------------
All options that are available in the python library *requests* can be set through
the client, this enables you to configure custom SSL certificate validation, send
client certificates if your API server requires them, and many other options.

For example to send a client certificate with every request

.. code:: python

   >>> from ansys.openapi.common import SessionConfiguration
   >>> configuration = SessionConfiguration(
   ...    client_cert_path='./my-client-cert.pem',
   ...    client_cert_key='secret-key'
   ... )
   >>> client.configuration = configuration

Platform-specific Kerberos Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ubuntu 20.04
^^^^^^^^^^^^

Ubuntu requires the python module ``gssapi`` to be built from source, this requires the Kerberos headers, Python headers
for the version of Python you are using, and a supported compiler (GCC works well).

You should then be able to install this module with the ``[linux-kerberos]`` extra.

.. code-block:: sh

   sudo apt install build-essentials python3.8-dev libkrb5-dev
   pip install ansys-openapi-common[linux-kerberos]

Once the installation completes, ensure your ``krb5.conf`` file is set up correctly for your Kerberos configuration, and
that you have a valid keytab file (normally at ``/etc/krb5.keytab``).

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
