import logging

from ._session import ApiClientFactory
from ._util import SessionConfiguration
from ._exceptions import ApiConnectionException, ApiException, AuthenticationWarning
from ._api_client import ApiClient

logging.basicConfig(
    format="%(asctime)s\t%(levelname)s\t%(message)s", level=logging.DEBUG
)

__all__ = [
    "ApiClient",
    "ApiClientFactory",
    "SessionConfiguration",
    "ApiException",
    "ApiConnectionException",
    "AuthenticationWarning",
]


__version__ = "0.1.0dev"
