import logging
import os
import warnings
from typing import Dict, Any, Tuple, Union, Container, Optional, Mapping

import requests
from urllib3.util.retry import Retry  # type: ignore
from requests.adapters import HTTPAdapter
from requests.auth import HTTPBasicAuth  # type: ignore
from requests_ntlm import HttpNtlmAuth  # type: ignore

from ._api_client import ApiClient
from ._oidc import OIDCSessionFactory
from ._util import (
    parse_authenticate,
    SessionConfiguration,
    set_session_kwargs,
)
from ._exceptions import ApiConnectionException, AuthenticationWarning

logger = logging.getLogger("pyansys.grantami.common")

TYPE_CHECKING = False
if TYPE_CHECKING:
    from ._util import CaseInsensitiveOrderedDict

_oidc_enabled = True
_platform_windows = False

try:
    # noinspection PyUnresolvedReferences
    import requests_oauthlib  # type: ignore
    import keyring
except ImportError:
    _oidc_enabled = False

if os.name == "nt":
    # noinspection PyUnresolvedReferences
    from requests_negotiate_sspi import HttpNegotiateAuth as NegotiateAuth  # type: ignore

    _platform_windows = True
else:
    # noinspection PyUnresolvedReferences
    from requests_kerberos import HTTPKerberosAuth as NegotiateAuth  # type: ignore

    _platform_windows = False


class ApiClientFactory:

    _session: requests.Session
    _sl_url: str
    _auth_header: "CaseInsensitiveOrderedDict"
    _configured: bool

    def __init__(
        self, servicelayer_url: str, session_configuration: SessionConfiguration = None
    ) -> None:
        """Create a factory that configures an API client for use with autogenerated Swagger clients.

        Handles setting up retry strategy, session-level timeout and any additional requests configuration,
        authentication must be subsequently configured using one of the other class methods.

        Parameters
        ----------
        servicelayer_url : str
           Base URL of the API server.
        session_configuration : Optional[SessionConfiguration]
           Additional configuration settings for the requests Session.
        """
        self._session = requests.Session()
        self._sl_url = servicelayer_url
        self._configured = False
        logger.info(f"[TECHDOCS]Creating new session at '{servicelayer_url}")

        if session_configuration is None:
            session_configuration = SessionConfiguration()
        self._session_configuration = session_configuration

        logger.debug(
            f"[TECHDOCS]Setting requests session parameter 'max_retries' "
            f"with value '{self._session_configuration.retry_count}'"
        )
        logger.debug(
            f"[TECHDOCS]Setting requests session parameter 'timeout' "
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
                    f"[TECHDOCS]Setting requests session parameter '{k}' with value '{v}'"
                )
        set_session_kwargs(self._session, config_dict)
        logger.info("[TECHDOCS]Base session created")

    def _validate_builder(self) -> None:
        if not self._configured:
            raise ValueError("No authentication yet configured")

    def build(self) -> ApiClient:
        """Finalizes the API client and returns it for use.

        Authentication must be configured for this method to succeed.

        Returns
        -------
        Configured API client.

        Raises
        ------
        ValueError
            When the client is not fully configured.
        """
        self._validate_builder()
        return ApiClient(self._session, self._sl_url, self._session_configuration)

    def with_anonymous(self) -> "ApiClientFactory":
        """Set up the client authentication for anonymous use. This does not configure any authentication or
        authorization headers, users must provide any authentication information required themselves.

        Clients relying on custom authentication such as client certificates, or non-standard tokens should use this
        method.

        Returns
        -------
        Client factory with configured authentication.
        """
        if self.__test_connection():
            logger.info("[TECHDOCS]Connection success")
            self._configured = True
            return self
        assert False, "[TECHDOCS]Connection failures will throw above"

    def with_credentials(
        self, username: str, password: str, domain: str = None
    ) -> "ApiClientFactory":
        """Set up the client authentication for use with provided credentials.

        This method will attempt to connect to the API and use the provided WWW-Authenticate header to determine whether
        Negotiate, NTLM, or Basic Authentication should be used. The selected authentication method will then be
        configured for use.

        Parameters
        ----------
        username : str
            Username for connection.
        password : str
            Password for connection.
        domain : Optional[str]
            Domain to use for connection if required.

        Returns
        -------
        Client factory with configured authentication.
        """
        logger.info(f"[TECHDOCS]Setting credentials for user '{username}")
        if domain is not None:
            username = f"{domain}\\{username}"
            logger.debug(
                f"[TECHDOCS]Setting domain for username, connecting as '{username}'"
            )

        initial_response = self._session.get(self._sl_url)
        if self.__handle_initial_response(initial_response):
            return self
        headers = self.__get_authenticate_header(initial_response)
        logger.debug(
            "[TECHDOCS]Detected authentication methods: "
            + ", ".join([method for method in headers.keys()])
        )
        if "Negotiate" in headers or "NTLM" in headers:
            logger.debug("[TECHDOCS]Attempting to connect with NTLM authentication...")
            self._session.auth = HttpNtlmAuth(username, password)
            if self.__test_connection():
                logger.info("[TECHDOCS]Connection success")
                self._configured = True
                return self
        if "Basic" in headers:
            logger.debug("[TECHDOCS]Attempting connection with Basic authentication...")
            self._session.auth = HTTPBasicAuth(username, password)
            if self.__test_connection():
                logger.info("[TECHDOCS]Connection success")
                self._configured = True
                return self
        raise ConnectionError("[TECHDOCS]Unable to connect with credentials.")

    def with_autologon(self) -> "ApiClientFactory":
        """Set up the client authentication for use with Kerberos (also known as integrated windows authentication).

        Returns
        -------
        Client factory with configured authentication.

        Notes
        -----
        Requires the user to have a valid Kerberos Ticket-Granting-Ticket (TGT). On Windows this is provided by default,
        on Linux this must be configured manually. See `here <https://github.com/requests/requests-kerberos>`_ for more
        information on how to configure this.
        """
        initial_response = self._session.get(self._sl_url)
        if self.__handle_initial_response(initial_response):
            return self
        headers = self.__get_authenticate_header(initial_response)
        logger.debug(
            "[TECHDOCS]Detected authentication methods: "
            + ", ".join([method for method in headers.keys()])
        )
        if "Negotiate" in headers:
            logger.debug(
                f"[TECHDOCS]Using {NegotiateAuth.__qualname__} as a Negotiate backend."
            )
            logger.debug(
                "[TECHDOCS]Attempting connection with Negotiate authentication..."
            )
            self._session.auth = NegotiateAuth()
            if self.__test_connection():
                logger.info("[TECHDOCS]Connection success")
                self._configured = True
                return self
        raise ConnectionError("[TECHDOCS]Unable to connect with autologon.")

    def with_oidc(
        self,
        access_token: str = None,
        refresh_token: str = None,
        use_cached_tokens: bool = False,
        login_timeout: int = 60,
        idp_session_configuration: SessionConfiguration = None,
    ) -> "ApiClientFactory":
        """Set up the client authentication for use with OpenID Connect.

        Parameters
        ----------
        access_token : Optional[str]
            Access token for authentication, if provided it will be used rather than interactive login.
        refresh_token : Optional[str]
            Refresh token for authentication, if provided it will be used rather than interactive login.
        use_cached_tokens : bool, default False
            Fetch access and refresh tokens from the key vault if available. This may require additional setup on linux,
            see 'here <https://github.com/jaraco/keyring>`_ for more information on configuring the keyvault
            on different platforms.
        login_timeout : int, default 60
            Length of time in seconds to wait for user to login interactively.
        idp_session_configuration : Optional[SessionConfiguration]
            Additional configuration settings for the requests Session when connected to the OpenID Identity Provider.

        Returns
        -------
        Client factory with configured authentication.

        Notes
        -----
        OIDC Authentication requires the `[oidc]` extra to be installed.
        """
        if not _oidc_enabled:
            raise ImportError(
                "[TECHDOCS]OIDC features are not enabled, to use them run `pip install openapi-client-common[oidc]`"
            )
        initial_response = self._session.get(self._sl_url)
        if self.__handle_initial_response(initial_response):
            return self
        bearer_info = OIDCSessionFactory.parse_unauthorized_header(initial_response)
        if use_cached_tokens:
            refresh_token = keyring.get_password(
                "MIScriptingToolkit_RefreshToken", self._sl_url
            )
            if refresh_token is None:
                raise ValueError(
                    "No stored credentials found, use the python STK to persist token credentials"
                )
        session_factory = OIDCSessionFactory(
            self._session,
            bearer_info,
            login_timeout,
            self._session_configuration,
            idp_session_configuration,
        )
        if access_token is not None or refresh_token is not None:
            self._session = session_factory.with_token(access_token, refresh_token)
        else:
            self._session = session_factory.authorize()
        self._configured = True
        return self

    def from_stk(
        self,
        stk_configuration: Dict[str, Any],
        oidc_authorize_timeout: int = 60,
        oidc_idp_session_configuration: SessionConfiguration = None,
    ) -> "ApiClientFactory":
        """Set up the client authentication using the configured authentication from a Granta MI STK session.

        Parameters
        ----------
        stk_configuration : Dict
            Configuration dictionary provided by the Granta MI STK session.
        oidc_authorize_timeout : int, default 60
            Length of time in seconds to wait for user to login interactively.
        oidc_idp_session_configuration : Optional[SessionConfiguration]
            Additional configuration settings for the requests Session when connected to the OpenID Identity Provider.

        Returns
        -------
        Client factory with configured authentication.

        Notes
        -----
        Requires the user to have the Granta MI Scripting Toolkit installed with at least version {INSERT_VERSION},
        otherwise use the appropriate class method to configure the requests session.
        """
        mode = stk_configuration["mode"]
        if mode == "autologon":
            return self.with_autologon()
        elif mode == "credential":
            username = stk_configuration["parameters"]["username"]
            password = stk_configuration["parameters"]["username"]
            domain = stk_configuration["parameters"]["username"]
            return self.with_credentials(username, password, domain)
        elif mode == "oidc":
            access_token = stk_configuration["parameters"]["access_token"]
            refresh_token = stk_configuration["parameters"]["refresh_token"]
            use_cached_tokens = stk_configuration["parameters"]["use_cached_tokens"]
            return self.with_oidc(
                access_token,
                refresh_token,
                use_cached_tokens,
                login_timeout=oidc_authorize_timeout,
                idp_session_configuration=oidc_idp_session_configuration,
            )
        else:
            raise KeyError(f"[TECHDOCS]Invalid mode: {mode}")

    def __test_connection(self) -> bool:
        """[TECHDOCS]Method attempts to connect to API server, if this returns a 2XX status code the method returns
        True, else the method will throw a :obj:`APIConnectionError` with the status code and the reason phrase. If the
        underlying requests method returns an exception of its own it is left to propagate as-is (for example a
        :obj:`~requests.exceptions.SSLException` if the remote certificate is untrusted).

        Returns
        -------
        True if the connection is valid, otherwise raises an exception.

        Raises
        ------
        APIConnectionError
            If the API server returns a status code other than 2XX.
        """
        resp = self._session.get(self._sl_url)
        if 200 <= resp.status_code < 300:
            return True
        else:
            raise ApiConnectionException(resp.status_code, resp.reason, resp.text)

    def __handle_initial_response(
        self, initial_response: requests.Response
    ) -> "Optional[ApiClientFactory]":
        """[TECHDOCS]Verifies that an initial 401 is returned if we expect to require authentication. If a 2XX response
        is returned then all is well, but we will not use any authentication in future. Otherwise something else has
        gone awry: return an :obj:`ApiConnectionException` with information about the response.

        Parameters
        ----------
        initial_response : requests.Response
            Response from querying the API server

        Raises
        ------
        ApiConnectionError
            If the API server returns a status code other than 2XX or 401

        Warns
        -----
        AuthenticationWarning
            If the connection succeeds when the user's requested authentication suggests it should fail.
        """
        if 200 <= initial_response.status_code < 300:
            warnings.warn(
                AuthenticationWarning(
                    "[TECHDOCS]Credentials were provided but server accepts anonymous "
                    "connections. Continuing without credentials."
                )
            )
            logger.info("[TECHDOCS]Connection success")
            self._configured = True
            return self
        elif initial_response.status_code != 401:
            raise ApiConnectionException(
                initial_response.status_code,
                initial_response.reason,
                initial_response.text,
            )
        else:
            return None

    @staticmethod
    def __get_authenticate_header(
        response: requests.Response,
    ) -> "CaseInsensitiveOrderedDict":
        """Helper method to extract the www-authenticate header from a requests response.

        Parameters
        ----------
        response : requests.Response
            Raw response from the API server.

        Returns
        -------
        Parsed contents of the www-authenticate header provided with the response.

        Throws
        ------
        ValueError
            If the response contains no www-authenticate header to be parsed.
        """
        if "www-authenticate" not in response.headers:
            raise ValueError(
                "[TECHDOCS]No www-authenticate header was provided, cannot continue..."
            )
        return parse_authenticate(response.headers["www-authenticate"])


class _RequestsTimeoutAdapter(HTTPAdapter):
    """Requests transport adapter to provide a default timeout for all requests sent to the API Server

    Attributes
    ----------
    timeout : int, default 31
        Time in seconds to wait for a response from the API server.
    """

    timeout: int = 31

    def __init__(self, *args, **kwargs):
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
        cert: Union[None, bytes, str, Container[Union[bytes, str]]] = None,
        proxies: Optional[Mapping[str, str]] = None,
    ) -> requests.Response:
        """Method called when sending a request to the API

        If no timeout is specified on the request then it is set to the provided value.

        Parameters
        ----------
        request : requests.PreparedRequest
            Request to the API
        stream : bool
            Whether to stream the request content.
        timeout : Union[None, float, Tuple[float, float], Tuple[float, None]]
            How long to wait for the server to send data before giving up, as a float, or a :ref:`(connect timeout,
            read timeout) <timeouts>` tuple.
        verify : Union[bool, str]
            Either a boolean, in which case it controls whether we verify the server's TLS certificate, or a string, in
            which case it must be a path to a CA bundle to use.
        cert : Union[None, bytes, str, Container[Union[bytes, str]]]
            User provided client certificate to send with the request, optionally with password.
        proxies : Optional[Mapping[str, str]]
            The proxies dictionary to apply to the request.

        Returns
        -------
        Response from the API.
        """
        if timeout is None:
            timeout = self.timeout
        return super().send(request, stream, timeout, verify, cert, proxies)
