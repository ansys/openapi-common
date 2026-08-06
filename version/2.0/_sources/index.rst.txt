OpenAPI-Common |version|
========================

.. toctree::
   :hidden:
   :maxdepth: 3

   api/index
   contributing


Introduction
------------
OpenAPI-Common is part of the larger `PyAnsys <https://docs.pyansys.com>`_
effort to facilitate the use of Ansys technologies directly from Python.

Because some Ansys products expose HTTP APIs rather than gRPC
APIs, this Python library provides a common client to consume
HTTP APIs, minimizing overhead and reducing code duplication.


Background
----------
A widely used standard for HTTP REST-style APIs is the OpenAPI standard,
formerly known as Swagger. OpenAPI-Common is designed to be used alongside
code generation tools to produce client libraries for HTTP APIs.


Brief example
-------------
This brief example demonstrates how the client works:

.. code:: python

    >>> from ansys.openapi.common import ApiClientFactory
    >>> client = ApiClientFactory("https://my-api.com")
    ...          .with_autologon()
    ...          .connect()
    >>> print(client)

    <ApiClient url: http://my-api.com>


The client is now ready and available for use with an OpenAPI client.

Authentication schemes
----------------------
OpenAPI-Common supports API servers configured with no authentication, API keys,
client certificates, and basic authentication.

Windows users can also use Windows Integrated Authentication to connect to Kerberos-enabled
APIs with their Windows credentials and to NTLM where it is supported.

Linux users can make use of Kerberos authentication via the ``[linux-kerberos]`` extra. This
requires a working installation of either MIT Kerberos or Heimdal, as well as some
platform-specific build steps. An additional requirement is a correctly configured ``krb5.keytab``
file on your system.

Windows and Linux users can authenticate with OIDC-enabled APIs by using the ``[oidc]`` extra.
Currently only the Authorization Code authentication flow is supported.

.. list-table:: Authentication methods by platform
   :header-rows: 1
   :widths: 30 15 15 40

   * - Authentication method
     - Windows
     - Linux
     - Builder method
   * - API Key
     - ✔️
     - ✔️
     - ``.with_anonymous()`` [1]_
   * - Basic
     - ✔️
     - ✔️
     - ``.with_credentials()``
   * - NTLM
     - ✔️
     - ❌
     - ``.with_credentials()``
   * - Kerberos
     - ✔️
     - ➕ [2]_
     - ``.with_autologon()``
   * - OIDC
     - ➕ [3]_
     - ➕ [3]_
     - ``.with_oidc()``

.. [1] Set the appropriate header in ``api_session_configuration``.
.. [2] When installed as ``pip install ansys-openapi-common[linux-kerberos]``.
.. [3] When installed as ``pip install ansys-openapi-common[oidc]``.

Advanced features
-----------------
You can set all options that are available in Python library *requests* through
the client. This enables you to configure custom SSL certificate validation, send
client certificates if your API server requires them, and configure many other options.

For example, to send a client certificate with every request:

.. code:: python

   >>> from ansys.openapi.common import SessionConfiguration
   >>> configuration = SessionConfiguration(
   ...    client_cert_path='./my-client-cert.pem',
   ...    client_cert_key='secret-key'
   ... )
   >>> client.configuration = configuration


Platform-specific Kerberos configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Kerberos authentication should be supported wherever the MIT or Heimdal Kerberos client
can be installed. OpenAPI-Common has been tested on the platforms that follow.
If you manage to use it on another platform, consider contributing installation steps for
your platform by making a pull request.

Ubuntu 20.04
^^^^^^^^^^^^

Ubuntu requires the ``gssapi`` Python module to be built from source. This requires the
Kerberos headers, Python headers for the version of Python that you are using, and a
supported compiler. (GCC works well.)

You should then be able to install this module with the ``[linux-kerberos]`` extra:

.. code-block:: sh

   sudo apt install build-essentials python3.8-dev libkrb5-dev
   pip install ansys-openapi-common[linux-kerberos]


Once the installation completes, ensure that your ``krb5.conf`` file is set up correctly
for your Kerberos configuration and that you have a valid ``keytab`` file, which is
normally in ``/etc/krb5.keytab``.

API reference
-------------
For comprehensive API documentation, see :doc:`API reference <api/index>`.

Contributions
-------------
Contributions to this library are welcome. For more information, see
:ref:`contributing_openapi`.

Project index
-------------

* :ref:`genindex`
