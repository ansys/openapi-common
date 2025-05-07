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

It is common to use a private CA in an organization to generate TLS certificates for internal resources. The
``requests`` library uses the ``certifi`` package which contains public CA certificates only, which means ``requests``
cannot verify private TLS certificates in its default configuration. The following error message is typically displayed
if a private TLS certificate is validated against the ``certifi`` public CAs:

.. code:: text

   requests.exceptions.SSLError: HTTPSConnectionPool(host='example.com', port=443): Max retries exceeded with url: /
   (Caused by SSLError(SSLCertVerificationError(1, '[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable
   to get local issuer certificate (_ssl.c:1028)')))``

If you encounter this error message, you should provide ``requests`` with the CA used to generate your private TLS
certificate. There are three recommended approaches to doing this, listed below in the order of simplicity.


1. `pip-system-certs`_
~~~~~~~~~~~~~~~~~~~~~~

The ``pip-system-certs`` library patches the certificate loading mechanism for ``requests`` to use the system
certificate store instead of the ``certifi`` store. Assuming the system certificate store includes the private CA, no
further action is required beyond installing ``pip-system-certs`` in the same virtual environment as this package.

.. warning::

   The change to ``requests`` affects every package in your environment, including pip. You **must** use a virtual
   environment when using ``pip-system-certs`` to avoid unexpected side-effects in other Python scripts.

This is recommended approach for Windows and Linux users. However, there are some situations in which
``pip-system-certs`` cannot be used:

* Your platform is not supported by ``pip-system-certs``.
* The private CA certificate has not been added to the system certificate store.
* The OpenSSL deployment used by Python is not configured to use the system certificate store (common when using
  conda-provided Python).

In these cases, the ``SSLCertVerificationError`` is still raised. Instead, provide the appropriate CA certificate to
``requests`` directly.


2. System CA certificate bundle (Linux only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :class:`~.SessionConfiguration` object allows you to provide a path to a file containing one or more CA
certificates. The custom CA certificate file is used instead of the ``certifi`` package to verify the service's TLS
certificate.

If you need to authenticate both internally- and publicly signed TLS certificates within the same environment, you must
use a CA bundle which contains both the internal and public CAs used to sign the TLS certificates.

.. note::

   OIDC authentication often requires validating internally- and publicly signed TLS certificates, since both internal
   and public resources are used to authenticate the resource.

CA bundles are often provided by Linux environments which include all trusted public CAs and any internal CAs added to
the system certificate store. These are available in the following locations:

* Ubuntu: ``/etc/ssl/certs/ca-certificates.crt``
* SLES: ``/var/lib/ca-certificates/ca-bundle.pem``
* RHEL/Rocky Linux: ``/etc/pki/tls/cert.pem``

For example, to use the system CA bundle in Ubuntu, use the following:

.. code:: python

   from ansys.openapi.common import SessionConfiguration

   config = SessionConfiguration(cert_store_path=/etc/ssl/certs/ca-certificates.crt)

This allows ``requests`` to correctly validate both internally and publicly signed TLS certificates, as long as the
internal CA certificate has been added to the system certificate store. If the internal CA certificate has not been
added to the system certificate store, then a ``SSLCertVerificationError`` is still raised, and you should proceed to
the next section.


3. Single CA certificate
~~~~~~~~~~~~~~~~~~~~~~~~

If you only need to authenticate internal TLS certificates, you can provide a path to the specific internal CA
certificate to be used for verification:

.. code:: python

   from ansys.openapi.common import SessionConfiguration

   config = SessionConfiguration(cert_store_path=/home/username/my_private_ca_certificate.pem)

Where ``/home/username/my_private_ca_certificate.pem`` is the path to the CA certificate file.

.. note::

   The ``cert_store_path`` argument overrides the ``certifi`` CA certificates. Providing a single private CA certificate
   causes ``requests`` to fail to validate publicly signed TLS certificates.


.. _pip-system-certs: https://gitlab.com/alelec/pip-system-certs
