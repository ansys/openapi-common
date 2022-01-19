"""Provides a helper to create sessions for use with Ansys OpenAPI clients."""

from ._session import ApiClientFactory
from ._util import SessionConfiguration, generate_user_agent
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

try:
    from importlib import metadata as metadata

    __version__ = metadata.version("ansys-openapi-common")
except ImportError:
    from importlib_metadata import metadata as metadata_backport

    __version__ = metadata_backport("ansys-openapi-common")["version"]
