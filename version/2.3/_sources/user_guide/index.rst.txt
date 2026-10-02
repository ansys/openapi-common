.. _ref_user_guide:

.. currentmodule:: ansys.openapi.common

User guide
##########

Basic usage
-----------

The :class:`.ApiClient` class is designed to be wrapped by code that implements a client
library. You should override the :meth:`~.ApiClient.__init__` or :meth:`~.connect` methods
to add additional required behavior.

Authentication is configured through the :class:`.ApiClientFactory` object and its
``with_xxx()`` methods. If no authentication is required, you can use the
:meth:`~.ApiClientFactory.with_anonymous()` method.

.. code:: python

   >>> from ansys.openapi.common import ApiClientFactory
   >>> session = ApiClientFactory('https://my-api.com/v1.svc')
   ...           .with_autologon()
   ...           .connect()
   <ApiClient url: https://my-api.com/v1.svc>


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


Session configuration
---------------------
You can set all options that are available in Python library *requests* through
the client with the :class:`~.SessionConfiguration` object. This enables you to
configure custom SSL certificate validation, send client certificates if your API
server requires them, and configure many other options.

For example, to send a client certificate with every request:

.. code:: python

   >>> from ansys.openapi.common import SessionConfiguration
   >>> configuration = SessionConfiguration(
   ...    client_cert_path='./my-client-cert.pem',
   ...    client_cert_key='secret-key'
   ... )
   >>> client.configuration = configuration


HTTPS certificates
------------------

The ``requests`` library uses the ``certifi`` package to verify TLS certificates instead of a local system certificate
store. These means only TLS certificates signed by a public CA can be verified by ``requests`` in its default
configuration. If you need to verify internally signed TLS certificates, there are two recommended approaches:

pip-system-certs
~~~~~~~~~~~~~~~~

The ``pip-system-certs`` library patches the certificate loading mechanism for ``requests`` causing it to
use your system certificate store. This is the simplest solution, but there are two potential limitations:

1. ``pip-system-certs`` does not support every platform that is supported by CPython, so it may not
be supported on your platform.

2. The change to ``requests`` affects every package in your environment, including pip. Make sure you are
using a virtual environment.

.. note::
  If you are using OIDC authentication and your service provides an internally signed certificate you must
  use this option.

Custom certificate store
~~~~~~~~~~~~~~~~~~~~~~~~

The :class:`~.SessionConfiguration` object allows you to provide a path to a custom CA certificate. If provided, the
custom CA certificate is used to verify the service's TLS certificate instead of the ``certifi`` package.
