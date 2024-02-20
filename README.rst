Overview
--------

OpenAPI-Common is intended for use with the custom code generation
template in the `PyAnsys project <https://github.com/pyansys>`_.
It provides the source code for an authentication-aware
client for OpenAPI client libraries.

OpenAPI-Common supports authentication with Basic, Negotiate, NTLM,
and OpenID Connect. Most features of the underlying requests session
are exposed for use. Some basic configuration is also provided by default.

Installation
------------

Install the ``openapi-common`` repository with this code:

.. code::

   pip install ansys-openapi-common

Alternatively, clone and install the repository with this code:

.. code::

   git clone https://github.com/pyansys/openapi-common
   cd openapi-common
   pip install .


Usage
-----

The API client class is intended to be wrapped by code that implements a client library.
You should override the ``__init__()`` or ``connect()`` method to add any
additional behavior that might be required.

Authentication is configured through the ``ApiClientFactory`` object and its ``with_xxx()``
methods. If no authentication is required, you can use the ``with_anonymous()`` method.
You can provide additional configuration with the ``SessionConfiguration`` object.

.. code:: python

   >>> from ansys.openapi.common import ApiClientFactory
   >>> session = ApiClientFactory('https://my-api.com/v1.svc')
   ...           .with_autologon()
   ...           .connect()
   <ApiClient url: https://my-api.com/v1.svc>


Authentication schemes
----------------------

OpenAPI-Common supports API servers configured with no authentication, API keys,
client certificates, and basic authentication schemes.

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

   * - Authentication method
     - Windows
     - Linux
     - Builder method
     - Additional settings
   * - API Key
     - ✔️
     - ✔️
     - ``.with_anonymous()``
     - Set the appropriate header in ``api_session_configuration``
   * - Client Certificate
     - ✔️
     - ✔️
     - Any
     - Provide ``client_cert_path`` and optionally ``client_cert_key`` in ``api_session_configuration``
   * - Basic
     - ✔️
     - ✔️
     - ``.with_credentials()``
     -
   * - NTLM
     - ✔️
     - ❌
     - ``.with_credentials()``
     -
   * - Kerberos
     - ✔️
     - ➕ with ``[linux-kerberos]`` extra
     - ``.with_autologon()``
     -
   * - OIDC
     - ➕ with ``[oidc]`` extra
     - ➕ with ``[oidc]`` extra
     - ``.with_oidc()``
     -

Platform-specific Kerberos configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Kerberos authentication should be supported wherever the MIT or Heimdal Kerberos client
can be installed. OpenAPI-Common has been tested on the platforms that follow.
If you manage to use it on another platform, consider contributing installation steps for
your platform by making a pull request.

Ubuntu 20.04
============

Ubuntu requires the ``gssapi`` Python module to be built from source. This requires the
Kerberos headers, Python headers for the version of Python that you are using (here we have
installed python3.10 from the deadsnakes ppa), and a supported compiler. (GCC works well.))

You should then be able to install this module with the ``[linux-kerberos]`` extra.

.. code-block:: bash

   sudo apt install build-essential python3.10-dev libkrb5-dev
   pip install ansys-openapi-common[linux-kerberos]


Once the installation completes, ensure that your ``krb5.conf`` file is set up correctly
for your Kerberos configuration and that you have a valid ``keytab`` file, which is
normally in ``/etc/krb5.keytab``.

License
-------
OpenAPI-Common is provided under the terms of the MIT license. You can find
the license text in the LICENSE file at the root of the repository.
