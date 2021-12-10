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
   >>> session = ApiClientFactory('https://my-api.com/v1.svc').with_autologon().connect()
   <ApiClient url: https://my-api.com/v1.svc>


License
-------

The library is provided under the terms of the MIT license, you can find the license text in the LICENSE file
at the root of the repository.
