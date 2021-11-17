import asyncio
import logging
import os
import threading
import webbrowser
from typing import Dict

import requests
from requests.models import CaseInsensitiveDict
from requests_oauthlib import OAuth2Session  # type: ignore

from ._util import (
    OIDCCallbackHTTPServer,
    parse_authenticate,
    SessionConfiguration,
    set_session_kwargs,
    RequestsConfiguration,
)

OIDC_HEADER_APPLICATION_NAME = "MI Scripting Toolkit"

TYPE_CHECKING = False
if TYPE_CHECKING:
    from . import SessionConfiguration

if os.getenv("VERBOSE_TOKEN_DEBUGGING"):
    _log_tokens = True
else:
    _log_tokens = False

logger = logging.getLogger("MI_Session")


class OIDCSessionFactory:
    """
    [TECHDOCS]Creates an OpenID Connect session with configuration fetched from MI server. Either uses provided token
    credentials, or can authorize a user with a browser-based interactive prompt.
    If your Identity provider does not provide the exact scopes requested by MI you will be unable to connect, to force
    the client to proceed with non-matching scopes set the environment variable `OAUTHLIB_RELAX_TOKEN_SCOPE` to `TRUE`.
    """

    def __init__(
        self,
        initial_session: requests.Session,
        bearer_information: CaseInsensitiveDict,
        login_timeout: int = 60,
        mi_requests_configuration: SessionConfiguration = None,
        idp_requests_configuration: SessionConfiguration = None,
    ) -> None:
        """
        [TECHDOCS]
        Parameters
        ----------
        initial_session : requests.Session
            Session for use whilst negotiating with the identity provider.
        login_timeout : int
            Number of seconds to wait for the user to authenticate, default 60s.
        mi_requests_configuration : SessionConfiguration
            Requests configuration settings for connections to the API server.
        idp_requests_configuration : SessionConfiguration
            Requests configuration settings for connections to the OpenID Identity Provider.

        Notes
        -----
        The `headers` field in `idp_requests_configuration` is not fully respected, the `accept` and
        `content-type` headers will be overridden. Other settings are respected.
        """
        self._callback_server: "OIDCCallbackHTTPServer"
        self._initial_session = initial_session
        self._oauth_session: OAuth2Session
        self._login_timeout = login_timeout

        logger.debug("[TECHDOCS]Creating OIDC session handler")

        if _log_tokens:
            logger.warning(
                "[TECHDOCS]Verbose token debugging is enabled, this will write sensitive information to the log. "
                "Do not use this in production."
            )
        self._authenticate_parameters = bearer_information

        if mi_requests_configuration is None:
            mi_requests_configuration = SessionConfiguration()

        if idp_requests_configuration is None:
            idp_requests_configuration = SessionConfiguration()

        self._mi_requests_configuration = (
            mi_requests_configuration.get_configuration_for_requests()
        )

        self._mi_requests_configuration["headers"][
            "X-Granta-ApplicationName"
        ] = OIDC_HEADER_APPLICATION_NAME

        idp_configuration = idp_requests_configuration.get_configuration_for_requests()

        self._idp_requests_configuration = OIDCSessionFactory._override_idp_header(
            idp_configuration
        )

        self._well_known_parameters = self._fetch_and_parse_well_known(
            self._authenticate_parameters["authority"]
        )

        self._add_api_audience_if_set()

        logger.info("[TECHDOCS]Configuring session...")

        def token_updater(token: Dict[str, str]) -> None:
            self.token = token
            self.access_token = token["access_token"]

        scopes = (
            self._authenticate_parameters["scope"]
            if "scope" in self._authenticate_parameters
            else []
        )
        self._oauth_session = OAuth2Session(
            client_id=self._authenticate_parameters["clientid"],
            redirect_uri=self._authenticate_parameters["redirecturi"],
            scope=scopes,
        )
        set_session_kwargs(self._oauth_session, self._mi_requests_configuration)
        if "offline_access" in scopes:
            logger.info("[TECHDOCS]Refresh tokens supported, configuring...")
            self._oauth_session.auto_refresh_url = self._well_known_parameters[
                "token_endpoint"
            ]
            self._oauth_session.auto_refresh_kwargs = {
                "client_id": self._authenticate_parameters["clientid"]
            }
            self._oauth_session.token_updater = token_updater
        self._callback_server = OIDCCallbackHTTPServer()
        logger.info("[TECHDOCS]_RequestsSession handler created.")

    @property
    def login_timeout(self) -> int:
        """[TECHDOCS]Time in seconds to wait for the user to authenticate via web browser.

        Returns
        -------
        Login timeout in seconds.
        """
        return self._login_timeout

    @login_timeout.setter
    def login_timeout(self, value: int) -> None:
        """
        Parameters
        ----------
        value : int
            Number of seconds to wait for the user to authenticate.
        """
        if isinstance(value, int):
            self._login_timeout = value
        else:
            raise TypeError("[TECHDOCS]Invalid value for login_timeout, must be int")

    @property
    def mi_requests_configuration(self) -> "SessionConfiguration":
        """[TECHDOCS]Configuration options for the requests session when communicating with the API server. See
        :class:`SessionConfiguration` for options to set.

        Returns
        -------
        Session configuration options for connection to API.
        """
        return SessionConfiguration.from_dict(self._mi_requests_configuration)

    @mi_requests_configuration.setter
    def mi_requests_configuration(self, value: "SessionConfiguration"):
        """
        Parameters
        ----------
        value : SessionConfiguration
            Requests session configuration for connections to the API server.
        """
        self._mi_requests_configuration = value.get_configuration_for_requests()
        self._add_api_audience_if_set()

    @property
    def idp_requests_configuration(self) -> "SessionConfiguration":
        """[TECHDOCS]Configuration options for the requests session when communicating with the OpenID Connect Identity
        Provider. See :class:`SessionConfiguration` for available options.

        Returns
        -------
        Session configuration options for connection to OpenID Identity Provider.

        Notes
        -----
        The `accept` and `content-type` headers will not be respected.
        """
        return SessionConfiguration.from_dict(self._idp_requests_configuration)

    @idp_requests_configuration.setter
    def idp_requests_configuration(self, value: "SessionConfiguration") -> None:
        """
        Parameters
        ----------
        value : SessionConfiguration
            Requests session configuration for connections to the OpenID Identity Provider.
        """
        self._idp_requests_configuration = OIDCSessionFactory._override_idp_header(
            value.get_configuration_for_requests()
        )
        self._add_api_audience_if_set()

    def with_token(
        self, access_token: str = None, refresh_token: str = None
    ) -> OAuth2Session:
        """[TECHDOCS] Finalizes and returns the underlying :class:`OAuth2Session` object with provided tokens

        If an access token is provided it will be used as-is, optionally provide a refresh token to allow automatic
        token renewal where supported. If neither are provided then the session will remain unconfigured and must be
        manually set up before use.

        Parameters
        ----------
        access_token : Optional[str]
            Access token for the API server, normally Base64 encoded JSON Web Token.
        refresh_token : Optional[str]
            Refresh token for the API server.

        Returns
        -------
        OpenID Connect supporting session object for use.
        """
        logger.info("[TECHDOCS]Setting tokens...")
        if access_token is not None:
            if _log_tokens:
                logger.debug(f"[TECHDOCS]Setting access token: {access_token}")
            self._oauth_session.token = {
                "token_type": "bearer",
                "access_token": access_token,
            }
        if refresh_token is not None:
            if _log_tokens:
                logger.debug(f"[TECHDOCS]Setting refresh token: {refresh_token}")
            # noinspection PyProtectedMember
            self._oauth_session._client.refresh_token = refresh_token
        return self._oauth_session

    def authorize(self) -> OAuth2Session:
        """[TECHDOCS] Finalizes creation of the underlying :class:`OAuth2Session` object, authorizing the user via their
        system web browser.

        Returns
        -------
        Authorized OpenID Connect supporting session object for use.
        """

        async def await_callback():
            thread = threading.Thread(target=self._callback_server.serve_forever)
            thread.daemon = True
            thread.start()
            return await self._callback_server.get_auth_code()

        authorization_url, state = self._oauth_session.authorization_url(
            self._well_known_parameters["authorization_endpoint"]
        )
        logger.info("[TECHDOCS]Authenticating user...")
        logger.debug(f"[TECHDOCS]Opening web browser with url {authorization_url}")
        webbrowser.open(authorization_url)
        auth_code = asyncio.wait_for(await_callback(), self._login_timeout)
        logger.info("[TECHDOCS]Authentication complete, fetching token...")
        if _log_tokens:
            logger.debug(f"[TECHDOCS]Received authorization code: {auth_code}")
        self._callback_server.shutdown()
        del self._callback_server

        _ = self._oauth_session.fetch_token(
            self._well_known_parameters["token_endpoint"],
            authorization_response=auth_code,
            include_client_id=True,
            **self._idp_requests_configuration,
        )
        if _log_tokens:
            logger.debug(f"[TECHDOCS]Access token: {self._oauth_session.token}")
            if self._oauth_session.auto_refresh_url is not None:
                logger.debug(
                    f"[TECHDOCS]Refresh token: {self._oauth_session._client.refresh_token}"
                )
        logger.info("[TECHDOCS]Tokens retrieved successfully, authentication complete.")
        return self._oauth_session

    @staticmethod
    def parse_unauthorized_header(
        unauthorized_response: "requests.Response",
    ) -> "CaseInsensitiveDict":
        """[TECHDOCS] Extract required parameters from the response's "WWW-Authenticate" header. Validates that OIDC is
        enabled and the all information required to configure the session is provided.

        Parameters
        ----------
        unauthorized_response : requests.Response
            Response obtained by fetching the target URI with no Authorization header.

        Returns
        -------
        Information provided in the WWW-Authenticate header, including at least the Authority, Client ID and
        redirect URI.
        """
        logger.debug("[TECHDOCS]Parsing bearer authentication parameters...")
        auth_header = unauthorized_response.headers["WWW-Authenticate"]
        authenticate_parameters = parse_authenticate(auth_header)
        if "bearer" not in authenticate_parameters:
            logger.debug(
                "[TECHDOCS]Detected authentication methods: "
                + ", ".join([method for method in authenticate_parameters.keys()])
            )
            raise ConnectionError(
                "[TECHDOCS]Unable to connect with OpenID Connect, not supported on this server."
            )
        mandatory_headers = ["redirecturi", "authority", "clientid"]
        missing_headers = []
        for header_name in mandatory_headers:
            if header_name not in authenticate_parameters["bearer"]:
                missing_headers.append(header_name)
        logger.debug(
            "[TECHDOCS]Detected bearer configuration headers: "
            + ", ".join(
                [parameter for parameter in authenticate_parameters["bearer"].keys()]
            )
        )
        if len(missing_headers) > 1:
            missing_header_string = '", "'.join(missing_headers)
            raise ConnectionError(
                f"[TECHDOCS]Unable to connect with OpenID Connect, mandatory headers '{missing_header_string}' "
                f"were not provided, cannot continue..."
            )
        elif len(missing_headers) == 1:
            raise ConnectionError(
                f"[TECHDOCS]Unable to connect with OpenID Connect, mandatory header '{missing_headers[0]}' "
                f"was not provided, cannot continue..."
            )
        else:
            return authenticate_parameters["bearer"]

    def _fetch_and_parse_well_known(self, url: str) -> CaseInsensitiveDict:
        """[TECHDOCS]Performs a GET request to the OpenID Identity Provider's well-known endpoint and verifies that the
        required parameters are returned.

        Parameters
        ----------
        url : str
            URL referencing the OpenID Identity Provider's well-known endpoint.

        Returns
        -------
        Well-known configuration information returned by the Identity Provider.
        """
        logger.info(
            f"[TECHDOCS]Fetching configuration information from identity provider {url}"
        )
        set_session_kwargs(self._initial_session, self._idp_requests_configuration)
        authority_response = self._initial_session.get(
            f"{url}.well-known/openid-configuration",
        )
        set_session_kwargs(self._initial_session, self._mi_requests_configuration)

        logger.debug("[TECHDOCS]Received configuration:")
        oidc_configuration = CaseInsensitiveDict(
            authority_response.json()
        )  # type: CaseInsensitiveDict

        mandatory_parameters = ["authorization_endpoint", "token_endpoint"]
        missing_headers = []
        for header_name in mandatory_parameters:
            if header_name not in oidc_configuration:
                missing_headers.append(header_name)

        logger.debug("[TECHDOCS]Detected well-known configuration: ")
        for k, v in oidc_configuration.items():
            logger.debug(f"{k}:\t{v}")

        if len(missing_headers) > 1:
            missing_headers_string = ", ".join(missing_headers)
            raise ConnectionError(
                f"[TECHDOCS]Unable to connect with OpenID Connect, mandatory well-known parameters "
                f"'{missing_headers_string}' were not provided, cannot continue..."
            )
        elif len(missing_headers) == 1:
            raise ConnectionError(
                f"[TECHDOCS]Unable to connect with OpenID Connect, well-known parameter '{missing_headers[0]}' "
                f"was not provided, cannot continue..."
            )

        return oidc_configuration

    @staticmethod
    def _override_idp_header(
        requests_configuration: RequestsConfiguration,
    ) -> RequestsConfiguration:
        """[TECHDOCS]Helper method to override user-provided Accept and Content-Type headers to ensure correct response
        from the OpenID Identity Provider.

        Parameters
        ----------
        requests_configuration : RequestsConfiguration
            Configuration options for connection to the OpenID Identity Provider.

        Returns
        -------
        Configuration with valid Accept and Content-Type headers for connection to the OpenID Identity Provider.
        """
        if requests_configuration["headers"] is not None:
            headers = requests_configuration["headers"]
            headers["accept"] = "application/json"
            headers["content-type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        return requests_configuration

    def _add_api_audience_if_set(self) -> None:
        """[TECHDOCS]Helper method to set the ApiAudience header on connections to the API if provided by the OpenID
        Identity Provider. This is mainly required for Auth0.
        """
        if "apiAudience" in self._authenticate_parameters:
            mi_headers: CaseInsensitiveDict = self._mi_requests_configuration["headers"]
            mi_headers["apiAudience"] = self._authenticate_parameters["apiAudience"]
            idp_headers: CaseInsensitiveDict = self._idp_requests_configuration[
                "headers"
            ]
            idp_headers["apiAudience"] = self._authenticate_parameters["apiAudience"]
