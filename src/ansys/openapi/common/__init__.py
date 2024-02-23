"""Provides a helper to create sessions for use with Ansys OpenAPI clients."""

from importlib import metadata as metadata

__version__ = metadata.version("ansys-openapi-common")

from ._api_client import ApiClient
from ._base import ApiBase, ApiClientBase, ModelBase, Unset, Unset_Type
from ._exceptions import (
    ApiConnectionException,
    ApiException,
    AuthenticationWarning,
    UndefinedObjectWarning,
)
from ._session import ApiClientFactory, OIDCSessionBuilder
from ._util import SessionConfiguration, generate_user_agent

__all__ = [
    "ApiClient",
    "ApiClientFactory",
    "SessionConfiguration",
    "ApiException",
    "ApiConnectionException",
    "AuthenticationWarning",
    "generate_user_agent",
    "OIDCSessionBuilder",
    "ApiBase",
    "ApiClientBase",
    "ModelBase",
    "UndefinedObjectWarning",
    "Unset",
    "Unset_Type",
]
