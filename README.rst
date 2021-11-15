Project Overview
----------------
The common library provides an authentication-aware client for OpenAPI client libraries.

It is intended for use with the custom code generation template available in the pyAnsys project, 
and currently supports authentication with Basic, Negotiate, NTLM, and OpenID Connect. Most features 
of the underlying requests session are exposed for use, and some basic configuration is provided by 
default.


Installation
------------

Install openapi-client-common with:

.. code::

   pip install ansys-grantami-common

Alternatively, clone and install in development mode with:

.. code::

   git clone https://github.com/pyansys/openapi-client-common
   cd openapi-client-common
   pip install -e .


Usage
-----
It's best to provide a sample code or even a figure demonstrating the usage of your library.  For example:

.. code:: python

   >>> from ansys.grantami.common import ApiClientFactory
   >>> session = ApiClientFactory('https://my-api.com/v1.svc').with_autologon().build()
   <ApiClient url: https://my-api.com/v1.svc>


License
-------

The library is provided under the terms of the MIT license, you can find the license text in the LICENSE file
at the root of the repository.

parse_authenticate and helpers are Copyright (c) 2015 Alexander Dutton under terms of the MIT license.

