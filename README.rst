|pyansys| |python| |pypi| |GH-CI| |MIT| |black| |pre-commit-ci|

.. |pyansys| image:: https://img.shields.io/badge/Py-Ansys-ffc107.svg?labelColor=black&logo=data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAIAAACQkWg2AAABDklEQVQ4jWNgoDfg5mD8vE7q/3bpVyskbW0sMRUwofHD7Dh5OBkZGBgW7/3W2tZpa2tLQEOyOzeEsfumlK2tbVpaGj4N6jIs1lpsDAwMJ278sveMY2BgCA0NFRISwqkhyQ1q/Nyd3zg4OBgYGNjZ2ePi4rB5loGBhZnhxTLJ/9ulv26Q4uVk1NXV/f///////69du4Zdg78lx//t0v+3S88rFISInD59GqIH2esIJ8G9O2/XVwhjzpw5EAam1xkkBJn/bJX+v1365hxxuCAfH9+3b9/+////48cPuNehNsS7cDEzMTAwMMzb+Q2u4dOnT2vWrMHu9ZtzxP9vl/69RVpCkBlZ3N7enoDXBwEAAA+YYitOilMVAAAAAElFTkSuQmCC
   :target: https://docs.pyansys.com/
   :alt: PyAnsys

.. |python| image:: https://img.shields.io/pypi/pyversions/ansys-openapi-common?logo=pypi
   :target: https://pypi.org/project/ansys-openapi-common/
   :alt: Python

.. |pypi| image:: https://img.shields.io/pypi/v/ansys-openapi-common.svg?logo=python&logoColor=white
   :target: https://pypi.org/project/ansys-openapi-common
   :alt: PyPI

.. |GH-CI| image:: https://github.com/pyansys/openapi-common/actions/workflows/ci_cd.yml/badge.svg
   :target: https://github.com/ansys/openapi-common/actions/workflows/ci_cd.yml
   :alt: GH-CI

.. |MIT| image:: https://img.shields.io/badge/License-MIT-yellow.svg
   :target: https://opensource.org/licenses/MIT
   :alt: MIT

.. |black| image:: https://img.shields.io/badge/code%20style-black-000000.svg?style=flat
   :target: https://github.com/psf/black
   :alt: Black

.. |pre-commit-ci| image:: https://results.pre-commit.ci/badge/github/ansys/openapi-common/main.svg
   :target: https://results.pre-commit.ci/latest/github/ansys/openapi-common/main
   :alt: pre-commit.ci status


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

HTTPS Certificates
~~~~~~~~~~~~~~~~~~

The ``requests`` library uses the ``certifi`` package to verify TLS certificates instead of a local system certificate store.
These means only TLS certificates signed by a public CA can be verified by ``requests`` in its default configuration. If you
need to verify internally-signed TLS certificates, there are two recommended approaches:

pip-system-certs
================

The ``pip-system-certs`` library patches the certificate loading mechanism for ``requests`` causing it to
use your system certificate store. This is the simplest solution, but there are two potential limitations:

1. ``pip-system-certs`` does not support every platform that is supported by CPython, so it may not
be supported on your platform.

2. The change to ``requests`` affects every package in your environment, including pip. Make sure you are
using a virtual environment.

.. note::
  If you are using OIDC authentication and your service provides a internally-signed certificate you will need
  to use this option.

Custom certificate store
========================

The ``SessionConfiguration`` object allows you to provide a path to a custom CA certificate. If provided, this will be
used to verify the service's TLS certificate instead of the ``certifi`` package.

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
