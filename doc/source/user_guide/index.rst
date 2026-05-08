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
The :class:`~.SessionConfiguration` class holds TLS settings, proxies, headers, redirects, and
timeouts. :class:`.ApiClientFactory` turns this into an :class:`httpx.Client` (with retries and
timeouts applied in OpenAPI-Common’s transport layer), which backs each :class:`.ApiClient`.

Use it to configure custom certificate validation, send client certificates if your API
server requires them, and adjust other transport options.

For example, to send a client certificate with every request:

.. code:: python

   >>> from ansys.openapi.common import ApiClientFactory, SessionConfiguration
   >>> configuration = SessionConfiguration(
   ...    client_cert_path='./my-client-cert.pem',
   ...    client_cert_key='secret-key',
   ... )
   >>> client = ApiClientFactory(
   ...    'https://my-api.com/v1.svc',
   ...    session_configuration=configuration,
   ... ).with_anonymous().connect()
   <ApiClient url: https://my-api.com/v1.svc>


HTTPS certificates
------------------

It is common to use a private CA in an organization to generate TLS certificates for internal resources. By
default, **httpx** verifies server certificates using the same **certifi** CA bundle that many Python HTTP
stacks use: it contains public roots only, so a server certificate issued by a private CA is not trusted unless
you add trust material (private CA file, merged bundle, or system-store integration).

If verification fails, Python typically surfaces ``ssl.SSLCertVerificationError``, sometimes wrapped by
**httpx** in a ``httpx.ConnectError`` when opening the TLS connection. For example:

.. code:: text

   ssl.SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed:
   unable to get local issuer certificate (_ssl.c:1000)

If you see this, point OpenAPI-Common at the CA that signed the server certificate (or a bundle that includes
it), using one of the options below.


1. `pip-system-certs`_
~~~~~~~~~~~~~~~~~~~~~~

The ``pip-system-certs`` package patches **certifi** so the default CA bundle reflects your operating system’s
certificate store instead of the bundled Mozilla list alone. Because **httpx** uses that default bundle for
verification unless you override it, installing ``pip-system-certs`` in the same environment as this library
often resolves trust for corporate CAs that are already in the system store.

.. warning::

   Changing **certifi**’s behaviour affects other libraries in that environment that rely on the same process-wide
   patching, including package installers. Use a **virtual environment** when enabling ``pip-system-certs`` to
   avoid unintended side effects outside your project.

This is the recommended approach for Windows and Linux when ``pip-system-certs`` is supported. It does **not** help
when the private CA is not in the system store, or when your Python build does not load the system store for
OpenSSL (common with some conda layouts). In those cases, pass a CA file or bundle explicitly (sections 2 and 3).


2. System CA certificate bundle (Linux only)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The :class:`~.SessionConfiguration` object allows you to provide a path to a file containing one or more CA
certificates. The file is used for TLS verification instead of the default **certifi** bundle.

If you need to validate both internal and public TLS endpoints in the same process, use a single bundle that
concatenates the internal CA(s) and the public roots you care about.

.. note::

   OIDC flows often touch both internal and public endpoints, so a merged bundle may be required.

CA bundles are often available on Linux machines that combine public and locally trusted anchors, for example:

* Ubuntu: ``/etc/ssl/certs/ca-certificates.crt``
* SLES: ``/var/lib/ca-certificates/ca-bundle.pem``
* RHEL/Rocky Linux: ``/etc/pki/tls/cert.pem``

For example, on Ubuntu:

.. code:: python

   from ansys.openapi.common import SessionConfiguration

   config = SessionConfiguration(cert_store_path="/etc/ssl/certs/ca-certificates.crt")

This lets the **httpx** client validate chains signed by CAs present in that bundle, provided the issuing CA for
your service is included. If your internal CA is not in the system bundle, continue to section 3.


3. Single CA certificate
~~~~~~~~~~~~~~~~~~~~~~~~

If you only need to trust a dedicated internal issuing CA, pass its certificate (PEM) as ``cert_store_path``:

.. code:: python

   from ansys.openapi.common import SessionConfiguration

   config = SessionConfiguration(
       cert_store_path="/home/username/my_private_ca_certificate.pem"
   )

where ``/home/username/my_private_ca_certificate.pem`` is the path to the PEM file.

.. note::

   When ``cert_store_path`` is set, that file **replaces** the default **certifi** bundle for verification. A PEM
   that contains only your private CA will **not** validate publicly issued sites unless those roots are also
   included in the same file or you use one of the other strategies above.


.. _pip-system-certs: https://gitlab.com/alelec/pip-system-certs
