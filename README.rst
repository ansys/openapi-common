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


OpenAPI-Common
==============

..
   _after-badges

OpenAPI Common is designed for use with the custom code generation
template in the `PyAnsys project <https://github.com/pyansys>`_.
It provides the source code for an authentication-aware client for
OpenAPI client libraries.

Background
----------
A widely used standard for HTTP REST-style APIs is the OpenAPI standard,
formerly known as Swagger. OpenAPI-Common is designed to be used alongside
code generation tools to produce client libraries for HTTP APIs.

Because some Ansys products expose HTTP APIs rather than gRPC
APIs, this Python library provides a common client to consume
HTTP APIs, minimizing overhead and reducing code duplication.

OpenAPI-Common supports authentication with Basic, Negotiate, NTLM,
and OpenID Connect. Most features of the underlying requests session
are exposed for use. Some basic configuration is also provided by default.

Dependencies
------------
.. readme_software_requirements

The ``ansys.openapi.common`` package currently supports Python version 3.10 through 3.13.

.. readme_software_requirements_end

Platform-specific Kerberos configuration
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. readme_kerberos

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

.. readme_kerberos_end


Installation
------------
.. readme_installation

To install the latest OpenAPI-Common release from `PyPI <https://pypi.org/project/ansys-openapi-common/>`_,
run this command:

.. code::

    pip install ansys-openapi-common

Alternatively, to install the latest development version from the `OpenAPI-Common repository <https://github.com/ansys/openapi-common>`_,
run this command:

.. code::

    pip install git+https://github.com/ansys/openapi-common.git


To install a local *development* version with Git and Poetry, run these commands:

.. code::

    git clone https://github.com/ansys/openapi-common
    cd openapi-common
    poetry install


The preceding commands install the package in development mode so that you can modify
it locally. Your changes are reflected in your Python setup after restarting the Python kernel.

.. readme_installation_end
