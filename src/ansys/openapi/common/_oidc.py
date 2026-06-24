# Copyright (C) 2022 - 2026 ANSYS, Inc. and/or its affiliates.
# SPDX-License-Identifier: MIT
#
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.
from typing import Any, Dict, List, Optional, Union
import urllib.parse

import keyring
import requests
from requests.models import CaseInsensitiveDict
from requests_auth import (  # type: ignore[import-untyped, unused-ignore]
    InvalidGrantRequest,
    OAuth2,
    OAuth2AuthorizationCodePKCE,
)

from ._logger import logger
from ._oidc_config import OIDCConfiguration
from ._util import (
    RequestsConfiguration,
    SessionConfiguration,
    parse_authenticate,
    set_session_kwargs,
)

_DEFAULT_SCOPES = ["openid", "offline_access"]

_ENDPOINT_CONFIGURATION_ERROR = (
    "OIDC configuration must include client_id and either well_known_url or both "
    "authorization_endpoint and token_endpoint."
)


class OIDCSessionFactory:
    """Builds authenticated API sessions from OpenID Connect configuration.

    Use :meth:`from_unauthorized_response` when parameters are discovered from a
    ``401`` response, or :meth:`from_configuration` when settings are provided upfront.

    Once constructed, the factory can supply a session using a stored token, a provided
    refresh token, an access token, or an interactive browser login.

    Notes
    -----
    The ``headers`` field in ``idp_session_configuration`` is not fully respected. The
    ``Accept`` and ``Content-Type`` headers will be overridden. Other settings are
    respected.
    """

    _api_url: str
    _oidc_config: OIDCConfiguration
    _api_session_configuration: RequestsConfiguration
    _idp_session_configuration: RequestsConfiguration
    _oauth_requests_session: requests.Session
    _authorized_session: requests.Session
    _auth: OAuth2AuthorizationCodePKCE

    @classmethod
    def _from_parsed_config(
        cls,
        api_url: str,
        oidc_config: OIDCConfiguration,
        initial_session: requests.Session,
        api_session_configuration: Optional[SessionConfiguration] = None,
        idp_session_configuration: Optional[SessionConfiguration] = None,
        *,
        default_scopes: bool = False,
    ) -> "OIDCSessionFactory":
        factory = cls.__new__(cls)
        factory._api_url = api_url
        factory._oidc_config = oidc_config
        factory._initialize_sessions(
            initial_session,
            api_session_configuration,
            idp_session_configuration,
        )
        factory._configure_oauth(default_scopes=default_scopes)
        return factory

    @classmethod
    def from_unauthorized_response(
        cls,
        initial_session: requests.Session,
        initial_response: requests.Response,
        api_session_configuration: Optional[SessionConfiguration] = None,
        idp_session_configuration: Optional[SessionConfiguration] = None,
    ) -> "OIDCSessionFactory":
        """Create a factory using parameters from the API ``401`` response.

        Parameters
        ----------
        initial_session : requests.Session
            Session to use while negotiating with the identity provider.
        initial_response : requests.Response
            Initial ``401`` response from the API server when no ``Authorization`` header
            is provided.
        api_session_configuration : SessionConfiguration, optional
            Configuration settings for connections to the API server.
        idp_session_configuration : SessionConfiguration, optional
            Configuration settings for connections to the OpenID identity provider.
        """
        logger.debug("Creating OIDC session handler from unauthorized response...")

        bearer_parameters = cls._parse_unauthorized_header(initial_response)
        oidc_config = cls._oidc_config_from_bearer(bearer_parameters)
        return cls._from_parsed_config(
            initial_response.url,
            oidc_config,
            initial_session,
            api_session_configuration,
            idp_session_configuration,
        )

    @classmethod
    def from_configuration(
        cls,
        api_url: str,
        oidc_configuration: OIDCConfiguration,
        initial_session: requests.Session,
        api_session_configuration: Optional[SessionConfiguration] = None,
        idp_session_configuration: Optional[SessionConfiguration] = None,
    ) -> "OIDCSessionFactory":
        """Create a factory using upfront OpenID Connect configuration.

        Parameters
        ----------
        api_url : str
            Base URL of the API server.
        oidc_configuration : OIDCConfiguration
            OpenID Connect provider settings.
        initial_session : requests.Session
            Session to use while negotiating with the identity provider.
        api_session_configuration : SessionConfiguration, optional
            Configuration settings for connections to the API server.
        idp_session_configuration : SessionConfiguration, optional
            Configuration settings for connections to the OpenID identity provider.
        """
        if not oidc_configuration.client_id:
            raise ValueError("OIDC configuration must include client_id.")

        if oidc_configuration.has_partial_endpoints():
            raise ValueError(
                "OIDC configuration must include both authorization_endpoint and "
                "token_endpoint when either is provided."
            )

        if (
            not oidc_configuration.has_explicit_endpoints()
            and not oidc_configuration.well_known_url
        ):
            raise ValueError(_ENDPOINT_CONFIGURATION_ERROR)

        logger.debug("Creating OIDC session handler from provided configuration...")

        return cls._from_parsed_config(
            api_url,
            oidc_configuration,
            initial_session,
            api_session_configuration,
            idp_session_configuration,
            default_scopes=True,
        )

    def _initialize_sessions(
        self,
        initial_session: requests.Session,
        api_session_configuration: Optional[SessionConfiguration],
        idp_session_configuration: Optional[SessionConfiguration],
    ) -> None:
        if api_session_configuration is None:
            api_session_configuration = SessionConfiguration()
        if idp_session_configuration is None:
            idp_session_configuration = SessionConfiguration()

        self._api_session_configuration = api_session_configuration.get_configuration_for_requests()
        self._idp_session_configuration = OIDCSessionFactory._override_idp_header(
            idp_session_configuration.get_configuration_for_requests()
        )

        self._oauth_requests_session = initial_session
        set_session_kwargs(self._oauth_requests_session, self._idp_session_configuration)

        self._authorized_session = requests.Session()
        set_session_kwargs(self._authorized_session, self._api_session_configuration)

    def _configure_oauth(self, default_scopes: bool = False) -> None:
        self._add_api_audience_if_set()
        well_known_parameters = self._resolve_oauth_endpoints()

        logger.info("Configuring session...")
        scopes = self._normalized_scopes(self._oidc_config.scopes, default_scopes=default_scopes)
        oauth_kwargs = self._redirect_uri_kwargs(self._oidc_config)
        if self._oidc_config.api_audience is not None:
            oauth_kwargs["audience"] = self._oidc_config.api_audience
        oauth_kwargs["client_id"] = self._oidc_config.client_id
        oauth_kwargs["scope"] = scopes
        oauth_kwargs["session"] = self._oauth_requests_session

        self._auth = OAuth2AuthorizationCodePKCE(
            authorization_url=well_known_parameters["authorization_endpoint"],
            token_url=well_known_parameters["token_endpoint"],
            **oauth_kwargs,
        )

        # If using Auth0 we cannot provide an audience with requests
        # to the token endpoint with grant_type=refresh_token. This
        # causes the token to be returned without the audience
        # required to access the user_info endpoint.
        self._auth.refresh_data.pop("audience", None)

        logger.info("Configuration complete.")

    def get_session_with_access_token(self, access_token: str) -> requests.Session:
        """Create a :class:`~requests.Session` object with provided access token.

        This method configures a session with the provided access token, if the token is invalid,
        or has expired, the session will be unable to authenticate.

        Parameters
        ----------
        access_token : str
            Access token for the API server, typically a Base-64 encoded JSON Web Token.
        """
        logger.info("Setting access token...")
        if access_token is None:
            raise ValueError("Must provide a value for 'access_token', not None")
        self._authorized_session.headers["Authorization"] = f"Bearer {access_token}"
        return self._authorized_session

    def get_session_with_provided_token(self, refresh_token: str) -> requests.Session:
        """Create a :class:`OAuth2Session` object with provided refresh token.

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
            state, token, expires_in, new_refresh_token = self._auth.refresh_token(refresh_token)
        except InvalidGrantRequest as excinfo:
            logger.debug(str(excinfo))
            raise ValueError("The provided refresh token was invalid, please request a new token.")
        # noinspection PyProtectedMember
        with OAuth2.token_cache._forbid_concurrent_missing_token_function_call:  # type: ignore[unused-ignore]
            # If we were provided with a new refresh token it's likely that the Identity
            # Provider is configured to rotate refresh tokens. Store the new one and
            # discard the old one. Otherwise, use the existing refresh token.
            if new_refresh_token is not None:
                refresh_token = new_refresh_token
            # noinspection PyProtectedMember
            OAuth2.token_cache._add_access_token(state, token, expires_in, refresh_token)
        self._authorized_session.auth = self._auth
        return self._authorized_session

    def get_session_with_stored_token(
        self,
        token_name: str = "ansys-openapi-common-oidc",  # nosec B107
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
    def _oidc_config_from_bearer(bearer_parameters: CaseInsensitiveDict) -> OIDCConfiguration:
        scopes: Optional[List[str]] = None
        if "scope" in bearer_parameters:
            scope_value = bearer_parameters["scope"]
            if isinstance(scope_value, str):
                scopes = scope_value.split()
            elif isinstance(scope_value, list):
                scopes = scope_value

        return OIDCConfiguration(
            client_id=bearer_parameters["clientid"],
            authority=bearer_parameters["authority"],
            redirect_uri=bearer_parameters.get("redirecturi"),
            scopes=scopes,
            api_audience=bearer_parameters.get("apiAudience"),
        )

    @staticmethod
    def _normalized_scopes(
        scopes: Optional[List[str]], *, default_scopes: bool = False
    ) -> Union[str, List[str]]:
        if scopes is None:
            if default_scopes:
                return " ".join(_DEFAULT_SCOPES)
            return []
        return " ".join(scopes)

    @staticmethod
    def _redirect_uri_kwargs(oidc_config: OIDCConfiguration) -> Dict[str, Any]:
        if oidc_config.redirect_uri:
            parsed = urllib.parse.urlparse(oidc_config.redirect_uri)
            if parsed.hostname:
                endpoint = parsed.path.lstrip("/")
                default_port = 443 if parsed.scheme == "https" else 80
                return {
                    "redirect_uri_domain": parsed.hostname,
                    "redirect_uri_port": parsed.port or default_port,
                    "redirect_uri_endpoint": endpoint,
                }
        return {"redirect_uri_port": oidc_config.redirect_uri_port}

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
        bearer_parameters: Optional["CaseInsensitiveDict"] = authenticate_parameters["bearer"]
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

    def _resolve_oauth_endpoints(self) -> CaseInsensitiveDict:
        if self._oidc_config.has_partial_endpoints():
            raise ValueError(
                "OIDC configuration must include both authorization_endpoint and "
                "token_endpoint when either is provided."
            )

        if self._oidc_config.has_explicit_endpoints():
            return CaseInsensitiveDict(
                {
                    "authorization_endpoint": self._oidc_config.authorization_endpoint,
                    "token_endpoint": self._oidc_config.token_endpoint,
                }
            )

        if self._oidc_config.well_known_url:
            return self._fetch_and_parse_well_known(self._oidc_config.well_known_url)

        if self._oidc_config.authority:
            authority = self._oidc_config.authority
            if not authority.endswith("/"):
                authority += "/"
            well_known_url = urllib.parse.urljoin(authority, ".well-known/openid-configuration")
            return self._fetch_and_parse_well_known(well_known_url)

        raise ValueError(_ENDPOINT_CONFIGURATION_ERROR)

    def _fetch_and_parse_well_known(self, well_known_url: str) -> CaseInsensitiveDict:
        """Fetch and process the required parameters from the well-known endpoint.

        Parameters
        ----------
        well_known_url : str
            OpenID Provider metadata URL.
        """
        logger.info(f"Fetching configuration information from {well_known_url}")
        authority_response = self._oauth_requests_session.get(well_known_url)

        logger.debug("Received configuration:")
        oidc_configuration = CaseInsensitiveDict(authority_response.json())  # type: CaseInsensitiveDict

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
        """Override user-provided ``Accept`` and ``Content-Type`` headers.

        Required to ensure correct response from the OpenID identity provider.

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
        """Set the ``ApiAudience`` header on connection to the API.

        Only add if provided by the OpenID identity provider. This is mainly required for Auth0.
        """
        if self._oidc_config.api_audience is None:
            return
        mi_headers: CaseInsensitiveDict = self._api_session_configuration["headers"]
        mi_headers["audience"] = self._oidc_config.api_audience
        idp_headers: CaseInsensitiveDict = self._idp_session_configuration["headers"]
        idp_headers["audience"] = self._oidc_config.api_audience
