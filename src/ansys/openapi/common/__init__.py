"""Provides a helper to create sessions for use with Ansys OpenAPI clients."""
import sys

if sys.version_info >= (3, 8):
    from importlib import metadata as metadata

    __version__ = metadata.version("ansys-openapi-common")
else:
    from importlib_metadata import metadata as metadata_backport

    __version__ = metadata_backport("ansys-openapi-common")["version"]

from ._api_client import ApiClient
from ._base import ApiBase, ApiClientBase, ModelBase
from ._exceptions import ApiConnectionException, ApiException, AuthenticationWarning
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
]
