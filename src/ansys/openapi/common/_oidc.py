from typing import Optional

import keyring
import requests
from requests.models import CaseInsensitiveDict
from requests_auth import InvalidGrantRequest  # type: ignore[import]
from requests_auth import OAuth2AuthorizationCodePKCE
from requests_auth.authentication import OAuth2  # type: ignore[import]

from ._logger import logger
from ._util import (
    RequestsConfiguration,
    SessionConfiguration,
    parse_authenticate,
    set_session_kwargs,
)

TYPE_CHECKING = False
if TYPE_CHECKING:
    from . import SessionConfiguration


class OIDCSessionFactory:
    """
    Creates an OpenID Connect session with the configuration fetched from the API server. This class uses either
    the provided token credentials or authorizes a user with a browser-based interactive prompt.

    Parameters
    ----------
    initial_session : requests.Session
        Session to use while negotiating with the identity provider.
    initial_response : requests.Response
        Initial 401 response from the API server when no ``Authorization`` header is provided.
    api_session_configuration : SessionConfiguration, optional
        Configuration settings for connections to the API server.
    idp_session_configuration : SessionConfiguration, optional
        Configuration settings for connections to the OpenID identity provider.

    Notes
    -----
    The ``headers`` field in ``idp_session_configuration`` is not fully respected. The ``Accept`` and
    ``Content-Type`` headers will be overridden. Other settings are respected.
    """

    def __init__(
        self,
        initial_session: requests.Session,
        initial_response: requests.Response,
        api_session_configuration: Optional[SessionConfiguration] = None,
        idp_session_configuration: Optional[SessionConfiguration] = None,
    ) -> None:
        self._initial_session = initial_session
        self._api_url = initial_response.url

        logger.debug("Creating OIDC session handler...")

        self._authenticate_parameters = self._parse_unauthorized_header(
            initial_response
        )

        if api_session_configuration is None:
            api_session_configuration = SessionConfiguration()
        if idp_session_configuration is None:
            idp_session_configuration = SessionConfiguration()

        self._api_session_configuration = (
            api_session_configuration.get_configuration_for_requests()
        )
        self._idp_session_configuration = OIDCSessionFactory._override_idp_header(
            idp_session_configuration.get_configuration_for_requests()
        )
        self._well_known_parameters = self._fetch_and_parse_well_known(
            self._authenticate_parameters["authority"]
        )

        self._add_api_audience_if_set()

        logger.info("Configuring session...")
        scopes = (
            self._authenticate_parameters["scope"]
            if "scope" in self._authenticate_parameters
            else []
        )

        self._auth = OAuth2AuthorizationCodePKCE(
            authorization_url=self._well_known_parameters["authorization_endpoint"],
            token_url=self._well_known_parameters["token_endpoint"],
            redirect_uri_port=32284,
            audience=self._authenticate_parameters["apiAudience"]
            if "apiAudience" in self._authenticate_parameters
            else None,
            client_id=self._authenticate_parameters["clientid"],
            scope=scopes,
            session=self._initial_session,
        )

        # If using Auth0 we cannot provide an audience with requests
        # to the token endpoint with grant_type=refresh_token. This
        # causes the token to be returned without the audience
        # required to access the user_info endpoint.
        self._auth.refresh_data.pop("audience", None)

        self._authorized_session = requests.Session()
        set_session_kwargs(self._authorized_session, self._api_session_configuration)
        logger.info("Configuration complete.")

    def get_session_with_provided_token(self, refresh_token: str) -> requests.Session:
        """Create a :class:`OAuth2Session` object with provided tokens.

        This method configures a session to request an access token with the provided refresh token,
        an access token will be requested immediately.

        Parameters
        ----------
        refresh_token : str
            Refresh token for the API server, typically a Base64-encoded JSON Web Token.
        """
        logger.info("Setting tokens...")
        if refresh_token is None:
            raise ValueError("Must provide a value for 'refresh_token', not None")
        try:
            state, token, expires_in, new_refresh_token = self._auth.refresh_token(
                refresh_token
            )
        except InvalidGrantRequest as excinfo:
            logger.debug(str(excinfo))
            raise ValueError(
                "The provided refresh token was invalid, please request a new token."
            )
        with OAuth2.token_cache.forbid_concurrent_missing_token_function_call:
            # If we were provided with a new refresh token it's likely that the Identity
            # Provider is configured to rotate refresh tokens. Store the new one and
            # discard the old one. Otherwise use the existing refresh token.
            if new_refresh_token is not None:
                refresh_token = new_refresh_token
            # noinspection PyProtectedMember
            OAuth2.token_cache._add_access_token(
                state, token, expires_in, refresh_token
            )
        self._authorized_session.auth = self._auth
        return self._authorized_session

    def get_session_with_stored_token(
        self, token_name: str = "ansys-openapi-common-oidc"
    ) -> requests.Session:
        """Create a :class:`OAuth2Session` object with a stored token.

        This method uses a token stored in the system keyring to authenticate the session. It requires a correctly
        configured system keyring backend.

        Parameters
        ----------
        token_name : str
            Name of the token key in the system keyring, used to identify tokens belonging to this package.

        Raises
        ------
        ValueError
            If no token is found in the system keyring with the provided ``token_name``.
        """
        refresh_token = keyring.get_password(token_name, self._api_url)
        if refresh_token is None:
            raise ValueError("No stored credentials found.")

        return self.get_session_with_provided_token(refresh_token=refresh_token)

    def get_session_with_interactive_authorization(
        self, login_timeout: int = 60
    ) -> requests.Session:
        """Create a :class:`OAuth2Session` object, authorizing the user via the system web browser.

        Parameters
        ----------
        login_timeout : int, optional
            Number of seconds to wait for the user to authenticate. The default is ``60s``.
        """

        self._auth.timeout = login_timeout
        self._authorized_session.auth = self._auth
        self._authorized_session.get(self._api_url)
        return self._authorized_session

    @staticmethod
    def _parse_unauthorized_header(
        unauthorized_response: "requests.Response",
    ) -> "CaseInsensitiveDict":
        """Extract required parameters from the response's ``WWW-Authenticate`` header.

        This method validates that OIDC is enabled and all information required to configure the session
        has been provided.

        Parameters
        ----------
        unauthorized_response : requests.Response
            Response obtained by fetching the target URI with no ``Authorization`` header.
        """
        logger.debug("Parsing bearer authentication parameters...")
        auth_header = unauthorized_response.headers["WWW-Authenticate"]
        authenticate_parameters = parse_authenticate(auth_header)
        if "bearer" not in authenticate_parameters:
            logger.debug(
                "Detected authentication methods: "
                + ", ".join([method for method in authenticate_parameters.keys()])
            )
            raise ConnectionError(
                "Unable to connect with OpenID Connect: not supported on this server."
            )

        mandatory_headers = ["redirecturi", "authority", "clientid"]
        missing_headers = []
        bearer_parameters: Optional["CaseInsensitiveDict"] = authenticate_parameters[
            "bearer"
        ]
        if bearer_parameters is None:
            bearer_parameters = CaseInsensitiveDict()

        for header_name in mandatory_headers:
            if header_name not in bearer_parameters:
                missing_headers.append(header_name)
        logger.debug(
            "Detected bearer configuration headers: "
            + ", ".join([parameter for parameter in bearer_parameters.keys()])
        )

        if len(missing_headers) > 1:
            missing_header_string = '", "'.join(missing_headers)
            raise ConnectionError(
                f"Unable to connect with OpenID Connect. Mandatory headers '{missing_header_string}' "
                f"were not provided. Cannot continue..."
            )
        elif len(missing_headers) == 1:
            raise ConnectionError(
                f"Unable to connect with OpenID Connect. Mandatory header '{missing_headers[0]}' "
                f"was not provided. Cannot continue..."
            )
        else:
            return bearer_parameters

    def _fetch_and_parse_well_known(self, url: str) -> CaseInsensitiveDict:
        """Perform a GET request to the OpenID identity provider's well-known endpoint and verify that the
        required parameters are returned.

        Parameters
        ----------
        url : str
            URL referencing the OpenID identity provider's well-known endpoint.
        """
        logger.info(f"Fetching configuration information from Identity Provider {url}")
        set_session_kwargs(self._initial_session, self._idp_session_configuration)
        authority_response = self._initial_session.get(
            f"{url}.well-known/openid-configuration",
        )
        set_session_kwargs(self._initial_session, self._api_session_configuration)

        logger.debug("Received configuration:")
        oidc_configuration = CaseInsensitiveDict(
            authority_response.json()
        )  # type: CaseInsensitiveDict

        mandatory_parameters = ["authorization_endpoint", "token_endpoint"]
        missing_headers = []
        for header_name in mandatory_parameters:
            if header_name not in oidc_configuration:
                missing_headers.append(header_name)

        logger.debug("Detected well-known configuration: ")
        for k, v in oidc_configuration.items():
            logger.debug(f"{k}:\t{v}")

        if len(missing_headers) > 1:
            missing_headers_string = ", ".join(missing_headers)
            raise ConnectionError(
                f"Unable to connect with OpenID Connect. Mandatory well-known parameters "
                f"'{missing_headers_string}' were not provided. Cannot continue..."
            )
        elif len(missing_headers) == 1:
            raise ConnectionError(
                f"Unable to connect with OpenID Connect. Well-known parameter '{missing_headers[0]}' "
                f"was not provided. Cannot continue..."
            )

        return oidc_configuration

    @staticmethod
    def _override_idp_header(
        requests_configuration: RequestsConfiguration,
    ) -> RequestsConfiguration:
        """Override user-provided ``Accept`` and ``Content-Type`` headers to ensure correct
        response from the OpenID identity provider.

        Parameters
        ----------
        requests_configuration : RequestsConfiguration
            Configuration options for connection to the OpenID identity provider.
        """
        if requests_configuration["headers"] is not None:
            headers = requests_configuration["headers"]
            headers["accept"] = "application/json"
            headers["content-type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        return requests_configuration

    def _add_api_audience_if_set(self) -> None:
        """Set the ``ApiAudience`` header on connection to the API, if provided by the OpenID
        identity provider. This is mainly required for Auth0.
        """
        if "apiAudience" not in self._authenticate_parameters:
            return
        mi_headers: CaseInsensitiveDict = self._api_session_configuration["headers"]
        mi_headers["audience"] = self._authenticate_parameters["apiAudience"]
        idp_headers: CaseInsensitiveDict = self._idp_session_configuration["headers"]
        idp_headers["audience"] = self._authenticate_parameters["apiAudience"]
