"""Provides a helper to create sessions for use with Ansys OpenAPI clients."""

import importlib.metadata

from ._session import ApiClientFactory
from ._util import SessionConfiguration
from ._exceptions import ApiConnectionException, ApiException, AuthenticationWarning
from ._api_client import ApiClient
from ._contrib.granta import create_session_from_granta_stk

__all__ = [
    "ApiClient",
    "ApiClientFactory",
    "SessionConfiguration",
    "ApiException",
    "ApiConnectionException",
    "AuthenticationWarning",
    "create_session_from_granta_stk",
]


__version__ = importlib.metadata.version("ansys-openapi-common")
