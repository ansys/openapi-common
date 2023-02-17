import os
import warnings
from typing import Tuple, Union, Container, Optional, Mapping, TypeVar, Any

import requests
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth
from requests_ntlm import HttpNtlmAuth  # type: ignore[import]

from . import __version__
from ._api_client import ApiClient
from ._util import (
    parse_authenticate,
    SessionConfiguration,
    set_session_kwargs,
    generate_user_agent,
)
from ._exceptions import ApiConnectionException, AuthenticationWarning
from ._logger import logger

TYPE_CHECKING = False
if TYPE_CHECKING:
    from ._util import CaseInsensitiveOrderedDict

_oidc_enabled = True
_linux_kerberos_enabled = True
_platform_windows = False

try:
    # noinspection PyUnresolvedReferences
    import requests_auth  # type: ignore[import]
    import keyring
    from ._oidc import OIDCSessionFactory
except ImportError:
    _oidc_enabled = False

if os.name == "nt":
    # noinspection PyUnresolvedReferences
    from requests_negotiate_sspi import HttpNegotiateAuth as NegotiateAuth  # type: ignore

    _platform_windows = True
else:
    try:
        # noinspection PyUnresolvedReferences
        from requests_kerberos import HTTPKerberosAuth as NegotiateAuth  # type: ignore

        _linux_kerberos_enabled = True
    except ImportError:
        _linux_kerberos_enabled = False

    _platform_windows = False

# Required to allow the ApiClientFactory to be subclassed. This ensures that Pylance
# understands that the subclass is returned by the builder methods instead of the base class
Api_Client_Factory = TypeVar("Api_Client_Factory", bound="ApiClientFactory")


class ApiClientFactory:
    """Creates a factory that configures an API client for use with autogenerated Swagger clients.

    This method handles setup of the retry strategy, session-level timeout, and any additional
    configurations for requests. Authentication must be configured afterwards using one of
    the other class methods.

    Parameters
    ----------
    api_url : str
       Base URL of the API server.
    session_configuration : SessionConfiguration, optional
       Additional configuration settings for the requests session.
    """

    _session: requests.Session
    _api_url: str
    _auth_header: "CaseInsensitiveOrderedDict"
    _configured: bool

    def __init__(
        self, api_url: str, session_configuration: Optional[SessionConfiguration] = None
    ) -> None:
        self._session = requests.Session()
        self._api_url = api_url
        self._configured = False
        logger.info(f"Creating new session at '{api_url}")

        if session_configuration is None:
            session_configuration = SessionConfiguration()

        if "User-Agent" not in session_configuration.headers:
            user_agent = generate_user_agent("ansys-openapi-common", __version__)
            session_configuration.headers["User-Agent"] = user_agent
        self._session_configuration = session_configuration

        logger.debug(
            f"Setting requests session parameter 'max_retries' "
            f"with value '{self._session_configuration.retry_count}'"
        )
        logger.debug(
            f"Setting requests session parameter 'timeout' "
            f"with value '{self._session_configuration.request_timeout}'"
        )

        retry_strategy = Retry(
            total=self._session_configuration.retry_count,
            backoff_factor=1,
            status_forcelist=[400, 429, 500, 502, 503, 504],
        )

        transport_adapter = _RequestsTimeoutAdapter(
            timeout=self._session_configuration.request_timeout,
            max_retries=retry_strategy,
        )
        self._session.mount("https://", transport_adapter)
        self._session.mount("http://", transport_adapter)

        config_dict = self._session_configuration.get_configuration_for_requests()
        for k, v in config_dict.items():
            if v is not None:
                logger.debug(
                    f"Setting requests session parameter '{k}' with value '{v}'"
                )
        set_session_kwargs(self._session, config_dict)
        logger.info("Base session created.")

    def _validate_builder(self) -> None:
        if not self._configured:
            raise ValueError("No authentication configured yet.")

    def connect(self) -> ApiClient:
        """Finalize the API client and return it for use.

        Authentication must be configured for this method to succeed.

        Returns
        -------
        :class:`ApiClient`
            Client object that can be used to connect to the server and perform API operations.

        Raises
        ------
        ValueError
            When the client is not fully configured.
        """
        self._validate_builder()
        return ApiClient(self._session, self._api_url, self._session_configuration)

    def with_anonymous(self: Api_Client_Factory) -> Api_Client_Factory:
        """Set up client authentication for anonymous use. This does not configure any authentication or
        authorization headers. Users must provide any authentication information required themselves.

        Clients relying on custom authentication such as client certificates or non-standard tokens should use this
        method.

        Returns
        -------
        :class:`~ansys.openapi.common.ApiClientFactory`
            Original client factory object.
        """
        if self.__test_connection():
            logger.info("Connection successful.")
            self._configured = True
            return self
        assert False, "Connection failures will throw above"

    def with_credentials(
        self: Api_Client_Factory,
        username: str,
        password: str,
        domain: Optional[str] = None,
    ) -> Api_Client_Factory:
        """Set up client authentication for use with provided credentials.

        This method will attempt to connect to the API and uses the provided ``WWW-Authenticate`` header to determine
        whether Negotiate, NTLM, or Basic Authentication should be used. The selected authentication method will then be
        configured for use.

        Parameters
        ----------
        username : str
            Username for the connection.
        password : str
            Password for the connection.
        domain : str, optional
            Domain to use for connection if required. The default is ``None``.

        Returns
        -------
        :class:`~ansys.openapi.common.ApiClientFactory`
            Original client factory object.

        Notes
        -----
        NTLM authentication is not currently supported on Linux.
        """
        logger.info(f"Setting credentials for user '{username}'.")
        if domain is not None:
            username = f"{domain}\\{username}"
            logger.debug(f"Setting domain for username, connecting as '{username}'.")

        initial_response = self._session.get(self._api_url)
        if self.__handle_initial_response(initial_response):
            return self
        headers = self.__get_authenticate_header(initial_response)
        logger.debug(
            "Detected authentication methods: "
            + ", ".join([method for method in headers.keys()])
        )
        if "Negotiate" in headers or "NTLM" in headers:
            if _platform_windows:
                logger.debug("Attempting to connect with NTLM authentication...")
                self._session.auth = HttpNtlmAuth(username, password)
                if self.__test_connection():
                    logger.info("Connection successful.")
                    self._configured = True
                    return self
        if "Basic" in headers:
            logger.debug("Attempting connection with Basic authentication...")
            self._session.auth = HTTPBasicAuth(username, password)
            if self.__test_connection():
                logger.info("Connection successful.")
                self._configured = True
                return self
        raise ConnectionError("Unable to connect with credentials provided.")

    def with_autologon(self: Api_Client_Factory) -> Api_Client_Factory:
        """Set up client authentication for use with Kerberos (also known as integrated Windows authentication).

        Returns
        -------
        :class:`~ansys.openapi.common.ApiClientFactory`
            Current client factory object.

        Notes
        -----
        Requires the user to have a valid Kerberos Ticket-Granting-Ticket (TGT).

        * On Windows, this is provided by default.
        * On Linux, this requires the ``[linux-kerberos]`` extension to be installed and your Kerberos installation
          to be configured correctly.
        """
        if not (_platform_windows or _linux_kerberos_enabled):
            raise ImportError(
                "Kerberos is not enabled. To use it, run `pip install ansys-openapi-common[linux-kerberos]`."
            )
        initial_response = self._session.get(self._api_url)
        if self.__handle_initial_response(initial_response):
            return self
        headers = self.__get_authenticate_header(initial_response)
        logger.debug(
            "Detected authentication methods: "
            + ", ".join([method for method in headers.keys()])
        )
        if "Negotiate" in headers:
            logger.debug(f"Using {NegotiateAuth.__qualname__} as a Negotiate backend.")
            logger.debug("Attempting connection with Negotiate authentication...")
            self._session.auth = NegotiateAuth()
            if self.__test_connection():
                logger.info("Connection successful.")
                self._configured = True
                return self
        raise ConnectionError("Unable to connect with autologon.")

    def with_oidc(
        self,
        idp_session_configuration: Optional[SessionConfiguration] = None,
    ) -> "OIDCSessionBuilder":
        """Set up client authentication for use with OpenID Connect.

        Parameters
        ----------
        idp_session_configuration : :class:`~ansys.openapi.common.SessionConfiguration`, optional
            Additional configuration settings for the requests session when connected to the OpenID identity provider.

        Returns
        -------
        :class:`~ansys.openapi.common.OIDCSessionBuilder`
            Builder object to authenticate via OIDC.

        Notes
        -----
        OIDC Authentication requires the ``[oidc]`` extra to be installed.
        """
        if not _oidc_enabled:
            raise ImportError(
                "OpenID Connect features are not enabled. To use them, run `pip install ansys-openapi-common[oidc]`."
            )
        initial_response = self._session.get(self._api_url)
        if self.__handle_initial_response(initial_response):
            return OIDCSessionBuilder(self)

        session_factory = OIDCSessionFactory(
            self._session,
            initial_response,
            self._session_configuration,
            idp_session_configuration,
        )

        return OIDCSessionBuilder(self, session_factory)

    def __test_connection(self) -> bool:
        """Attempt to connect to the API server. If this returns a 2XX status code, the method returns
        ``True``. Otherwise, the method will throw an :obj:`APIConnectionError` object with the status
        code and the reason phrase. If the underlying requests method returns an exception of its own,
        it is left to propagate as-is (for example, a
        :obj:`~requests.exceptions.SSLException` object if the remote certificate is untrusted).

        Raises
        ------
        APIConnectionError
            If the API server returns a status code other than 2XX.
        """
        resp = self._session.get(self._api_url)
        if 200 <= resp.status_code < 300:
            return True
        else:
            raise ApiConnectionException(resp)

    def __handle_initial_response(
        self, initial_response: requests.Response
    ) -> "Optional[ApiClientFactory]":
        """Verify that an initial 401 response is returned if we expect to require authentication. If a 2XX response
        is returned, then all is well, but we will not use any authentication in future. Otherwise, something else has
        gone awry: return an :obj:`ApiConnectionException` object with information about the response.

        Parameters
        ----------
        initial_response : requests.Response
            Response from querying the API server.

        Raises
        ------
        ApiConnectionError
            If the API server returns a status code other than 2XX or 401.

        Warns
        -----
        AuthenticationWarning
            If the connection succeeds when the user's requested authentication suggests it should fail.
        """
        if 200 <= initial_response.status_code < 300:
            warnings.warn(
                AuthenticationWarning(
                    "Credentials were provided but server accepts anonymous "
                    "connections. Continuing without credentials."
                )
            )
            logger.info("Connection successful.")
            self._configured = True
            return self
        elif initial_response.status_code != 401:
            raise ApiConnectionException(initial_response)
        else:
            return None

    @staticmethod
    def __get_authenticate_header(
        response: requests.Response,
    ) -> "CaseInsensitiveOrderedDict":
        """Extract the ``WWW-Authenticate`` header from a requests response.

        Parameters
        ----------
        response : requests.Response
            Raw response from the API server.

        Raises
        ------
        ValueError
            If the response contains no ``WWW-Authenticate`` header to be parsed.
        """
        if "www-authenticate" not in response.headers:
            raise ValueError(
                "No www-authenticate header was provided. Cannot continue..."
            )
        return parse_authenticate(response.headers["www-authenticate"])


class OIDCSessionBuilder:
    """Helps create OpenID Connect sessions from different types of input and provides OIDC-specific
    configuration options.

    Parameters
    ----------
    client_factory : ApiClientFactory
        Parent API client factory object that will be returned once configuration is complete.
    session_factory : OIDCSessionFactory, optional
        OIDC session factory object that will be configured and used to return an OAuth-supporting session.
    """

    def __init__(
        self,
        client_factory: ApiClientFactory,
        session_factory: "Optional[OIDCSessionFactory]" = None,
    ) -> None:
        self._client_factory = client_factory
        self._session_factory = session_factory

    def with_stored_token(
        self, token_name: str = "ansys-openapi-common-oidc"
    ) -> ApiClientFactory:
        """Use a token stored in the system keyring to authenticate the session. This method requires a correctly
        configured system keyring backend.

        Parameters
        ----------
        token_name : str
            Name of the token key in the system keyring.

        Returns
        -------
        :class:`ApiClientFactory`
           Original client factory object.

        Raises
        ------
        ValueError
            If no token is found in the system keyring with the provided ``token_name``.
        """
        if self._session_factory is None:
            return self._client_factory
        refresh_token = keyring.get_password(token_name, self._client_factory._api_url)
        if refresh_token is None:
            raise ValueError("No stored credentials found.")

        return self.with_token(refresh_token=refresh_token)

    def with_token(self, refresh_token: str) -> ApiClientFactory:
        """Use a provided refresh token to authenticate the session.

        The refresh token will be used to request a new access token from the Identity Provider,
        this will be automatically refreshed shortly before expiration.

        Parameters
        ----------
        refresh_token : str
            Refresh token.

        Returns
        -------
        :class:`ApiClientFactory`
            Original client factory object.
        """
        if self._session_factory is None:
            return self._client_factory
        self._client_factory._session = (
            self._session_factory.get_session_with_provided_token(
                refresh_token=refresh_token
            )
        )
        self._client_factory._configured = True
        return self._client_factory

    def authorize(self, login_timeout: int = 60) -> ApiClientFactory:
        """Authenticate the user interactively by opening a web browser and waiting for the user to log in.

        Parameters
        ----------
        login_timeout : int
            Time in seconds to wait for the user's web browser to authenticate. The default is ``60s``.

        Returns
        -------
        :class:`ApiClientFactory`
            Original client factory object.
        """
        if self._session_factory is None:
            return self._client_factory
        self._client_factory._session = (
            self._session_factory.get_session_with_interactive_authorization(
                login_timeout
            )
        )
        self._client_factory._configured = True
        return self._client_factory


class _RequestsTimeoutAdapter(HTTPAdapter):
    """Requests transport adapter to provide a default timeout for all requests sent to the API server.

    Attributes
    ----------
    timeout : int, optional
        Time in seconds to wait for a response from the API server. The default is ``31s``.
    """

    timeout: int = 31

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        if "timeout" in kwargs:
            self.timeout = kwargs["timeout"]
            del kwargs["timeout"]
        super().__init__(*args, **kwargs)

    def send(
        self,
        request: requests.PreparedRequest,
        stream: bool = False,
        timeout: Union[None, float, Tuple[float, float], Tuple[float, None]] = None,
        verify: Union[bool, str] = True,
        cert: Union[
            None, bytes, str, Tuple[Union[bytes, str], Union[bytes, str]]
        ] = None,
        proxies: Optional[Mapping[str, str]] = None,
    ) -> requests.Response:
        """Method called when sending a request to the API.

        If no timeout is specified on the request, it is set to the provided value.

        Parameters
        ----------
        request : requests.PreparedRequest
            Request to the API.
        stream : bool, optional
            Whether to stream the request content. The default is ``False``.
        timeout : Union[None, float, Tuple[float, float], Tuple[float, None]]
            How long to wait for the server to send data before giving up, as either a float or a
            :ref:`(connect timeout, read timeout) <timeouts>` tuple.
        verify : Union[bool, str]
            Either a Boolean that controls whether we verify the server's TLS certificate or a string
            that must be a path to a CA bundle to use.
        cert : None, bytes, str, Tuple[Union[bytes, str], Union[bytes, str]]
            User-provided client certificate to send with the request, optionally with password.
        proxies : Mapping[str, str], optional
            Dictionary of proxies to apply to the request.
        """
        return super().send(
            request, stream, timeout or self.timeout, verify, cert, proxies
        )
