Project Overview
----------------
The common library provides an authentication-aware client for OpenAPI client libraries.

It is intended for use with the custom code generation template available in the pyAnsys project, 
and currently supports authentication with Basic, Negotiate, NTLM, and OpenID Connect. Most features 
of the underlying requests session are exposed for use, and some basic configuration is provided by 
default.


Installation
------------

Install openapi-common with:

.. code::

   pip install ansys-openapi-common

Alternatively, clone and install in development mode with:

.. code::

   git clone https://github.com/pyansys/openapi-common
   cd openapi-common
   pip install -e .


Usage
-----
The API client class is intended to be wrapped by code that implements a client library,
it is suggested to override the ``__init__()`` or ``connect()`` methods to add any
additional behaviour that may be required.

Authentication is configured through the ``ApiClientFactory`` object and its ``with_xxx()``
methods, if no authentication is required you can use the ``with_anonymous()`` method.
Additional configuration can be provided with the ``SessionConfiguration`` object.

.. code:: python

   >>> from ansys.openapi.common import ApiClientFactory
   >>> session = ApiClientFactory('https://my-api.com/v1.svc')
   ...           .with_autologon()
   ...           .connect()
   <ApiClient url: https://my-api.com/v1.svc>


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

Platform-specific Kerberos Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Ubuntu 20.04
============

Ubuntu requires the python module ``gssapi`` to be built from source, this requires the Kerberos headers, Python headers
for the version of Python you are using, and a supported compiler (GCC works well).

You should then be able to install this module with the ``[linux-kerberos]`` extra.

.. code-block:: bash

   sudo apt install build-essentials python3.8-dev libkrb5-dev
   pip install ansys-openapi-common[linux-kerberos]

Once the installation completes, ensure your ``krb5.conf`` file is set up correctly for your Kerberos configuration, and
that you have a valid keytab file (normally at ``/etc/krb5.keytab``).

License
-------

The library is provided under the terms of the MIT license, you can find the license text in the LICENSE file
at the root of the repository.
