"""Provides a helper to create sessions for use with Ansys OpenAPI clients."""
from importlib import metadata as metadata

__version__ = metadata.version("ansys-openapi-common")

from ._session import ApiClientFactory, OIDCSessionBuilder
from ._util import SessionConfiguration, generate_user_agent
from ._exceptions import ApiConnectionException, ApiException, AuthenticationWarning
from ._api_client import ApiClient
from ._contrib.granta import create_session_from_granta_stk
from ._base import ApiBase, ApiClientBase, ModelBase

__all__ = [
    "ApiClient",
    "ApiClientFactory",
    "SessionConfiguration",
    "ApiException",
    "ApiConnectionException",
    "AuthenticationWarning",
    "create_session_from_granta_stk",
    "generate_user_agent",
    "OIDCSessionBuilder",
    "ApiBase",
    "ApiClientBase",
    "ModelBase",
]
