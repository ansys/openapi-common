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

import urllib.parse
from typing import Any, Optional

import httpx
import keyring
from httpx_auth import (
    InvalidGrantRequest,
    OAuth2,
    OAuth2AuthorizationCodePKCE,
)

from ._logger import logger
from ._util import (
    CaseInsensitiveOrderedDict,
    SessionConfiguration,
    TransportConfiguration,
    collect_www_authenticate_raw_values,
    create_httpx_client_from_session_configuration,
    parse_authenticate,
)


class OIDCSessionFactory:
    """
    Creates an OpenID Connect session with the configuration fetched from the API server.

    This class uses either the provided token credentials or authorizes a user with a browser-based
    interactive prompt.

    Parameters
    ----------
    initial_response : httpx.Response
        Initial 401 response from the API server when no ``Authorization`` header is provided.
    api_session_configuration : SessionConfiguration, optional
        Configuration settings for connections to the API server.
    idp_session_configuration : SessionConfiguration, optional
        Configuration settings for connections to the OpenID identity provider.

    Notes
    -----
    The ``headers`` field in ``idp_session_configuration`` is not fully respected on IdP HTTP
    clients: ``Accept`` and ``Content-Type`` are overridden by
    ``OIDCSessionFactory._override_idp_header``. Other settings apply to well-known discovery
    and token endpoint traffic. The initial ``GET`` to the resource server is performed with
    the factory's main client (constructor ``session_configuration`` only); it does not use
    this IdP mapping for that request.

    OAuth2 / token flows use :class:`httpx.Client` with ``httpx-auth`` (PKCE), aligned with the rest
    of the migration to ``httpx``.

    Token exchange and refresh POSTs to the identity provider use a dedicated IdP-configured client
    (from ``idp_session_configuration``), separate from the API client, so TLS settings such as a
    custom CA bundle apply to the IdP regardless of the API client's defaults (including HTTPX's
    certifi-based verification).
    """

    def __init__(
        self,
        initial_response: httpx.Response,
        api_session_configuration: Optional[SessionConfiguration] = None,
        idp_session_configuration: Optional[SessionConfiguration] = None,
    ) -> None:
        self._api_url = str(initial_response.url)

        logger.debug("Creating OIDC session handler...")

        self._authenticate_parameters = self._parse_unauthorized_header(initial_response)

        _api_sc = api_session_configuration or SessionConfiguration()
        _idp_sc = idp_session_configuration or SessionConfiguration()

        self._api_session_configuration = _api_sc.get_transport_configuration()
        idp_transport = OIDCSessionFactory._override_idp_header(
            _idp_sc.get_transport_configuration()
        )
        self._idp_session_configuration = idp_transport

        _discovery_sc = SessionConfiguration.from_dict(idp_transport)
        _discovery_sc.retry_count = _idp_sc.retry_count
        _discovery_sc.request_timeout = _idp_sc.request_timeout
        authority = self._authenticate_parameters["authority"]
        with create_httpx_client_from_session_configuration(
            _discovery_sc,
            mount_scheme_url=authority,
        ) as discovery_client:
            self._well_known_parameters = OIDCSessionFactory._fetch_and_parse_well_known(
                discovery_client,
                authority,
            )

        self._add_api_audience_if_set()

        oauth_sc = SessionConfiguration.from_dict(idp_transport)
        oauth_sc.retry_count = _idp_sc.retry_count
        oauth_sc.request_timeout = _idp_sc.request_timeout
        self._oauth_httpx_client = create_httpx_client_from_session_configuration(
            oauth_sc,
            mount_scheme_url=authority,
        )

        logger.info("Configuring session...")
        scopes_raw = self._authenticate_parameters.get("scope")
        scopes_list: list[str] = []
        if scopes_raw is not None and scopes_raw != []:
            if isinstance(scopes_raw, str):
                scopes_list = scopes_raw.split()
            elif isinstance(scopes_raw, (list, tuple)):
                scopes_list = [str(s) for s in scopes_raw]
            else:
                scopes_list = [str(scopes_raw)]

        pkce_kwargs: dict[str, Any] = {
            "redirect_uri_port": 32284,
            "client": self._oauth_httpx_client,
            "client_id": self._authenticate_parameters["clientid"],
        }
        if scopes_list:
            pkce_kwargs["scope"] = " ".join(scopes_list)
        if "apiAudience" in self._authenticate_parameters:
            pkce_kwargs["audience"] = self._authenticate_parameters["apiAudience"]

        self._auth = OAuth2AuthorizationCodePKCE(
            authorization_url=self._well_known_parameters["authorization_endpoint"],
            token_url=self._well_known_parameters["token_endpoint"],
            **pkce_kwargs,
        )

        # If using Auth0 we cannot send ``audience`` on refresh_token grants to the token
        # endpoint: the token is returned without the audience required for some APIs.
        self._auth.refresh_data.pop("audience", None)

        _api_client_sc = SessionConfiguration.from_dict(self._api_session_configuration)
        _api_client_sc.retry_count = _api_sc.retry_count
        _api_client_sc.request_timeout = _api_sc.request_timeout
        self._authorized_httpx_client = create_httpx_client_from_session_configuration(
            _api_client_sc,
            mount_scheme_url=self._api_url,
        )

        logger.info("Configuration complete.")

    def get_session_with_access_token(self, access_token: str) -> httpx.Client:
        """Create an :class:`~httpx.Client` with provided access token.

        This method configures a client with the provided access token, if the token is invalid,
        or has expired, the client will be unable to authenticate.

        Parameters
        ----------
        access_token : str
            Access token for the API server, typically a Base-64 encoded JSON Web Token.
        """
        logger.info("Setting access token...")
        if access_token is None:
            raise ValueError("Must provide a value for 'access_token', not None")
        self._authorized_httpx_client.headers["Authorization"] = f"Bearer {access_token}"
        return self._authorized_httpx_client

    def get_session_with_provided_token(self, refresh_token: str) -> httpx.Client:
        """Create an :class:`~httpx.Client` using the provided refresh token.

        This method configures a client to request an access token with the provided refresh token,
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
        with OAuth2.token_cache._forbid_concurrent_missing_token_function_call:  # type: ignore[unused-ignore]
            # If we were provided with a new refresh token it's likely that the Identity
            # Provider is configured to rotate refresh tokens. Store the new one and
            # discard the old one. Otherwise, use the existing refresh token.
            if new_refresh_token is not None:
                refresh_token = new_refresh_token
            OAuth2.token_cache._add_access_token(state, token, expires_in, refresh_token)
        self._authorized_httpx_client.auth = self._auth
        return self._authorized_httpx_client

    def get_session_with_stored_token(
        self, token_name: str = "ansys-openapi-common-oidc"
    ) -> httpx.Client:
        """Create an :class:`~httpx.Client` using a stored refresh token.

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

    def get_session_with_interactive_authorization(self, login_timeout: int = 60) -> httpx.Client:
        """Create an :class:`~httpx.Client`, authorizing the user via the system web browser.

        Parameters
        ----------
        login_timeout : int, optional
            Number of seconds to wait for the user to authenticate. The default is ``60s``.
        """
        self._auth.timeout = login_timeout
        self._authorized_httpx_client.auth = self._auth
        self._authorized_httpx_client.get(self._api_url)
        return self._authorized_httpx_client

    @staticmethod
    def _parse_unauthorized_header(
        unauthorized_response: httpx.Response,
    ) -> CaseInsensitiveOrderedDict:
        """Extract required parameters from the response's ``WWW-Authenticate`` header(s).

        This method validates that OIDC is enabled and all information required to configure the session
        has been provided.

        Parameters
        ----------
        unauthorized_response : httpx.Response
            Response obtained by fetching the target URI with no ``Authorization`` header.
        """
        logger.debug("Parsing bearer authentication parameters...")
        raw_values = collect_www_authenticate_raw_values(unauthorized_response)
        if not raw_values:
            raise ConnectionError(
                "Unable to connect with OpenID Connect: no www-authenticate header was provided."
            )
        authenticate_parameters_merged = CaseInsensitiveOrderedDict()
        for chunk in raw_values:
            authenticate_parameters_merged.update(parse_authenticate(chunk))
        if "bearer" not in authenticate_parameters_merged:
            logger.debug(
                "Detected authentication methods: "
                + ", ".join([method for method in authenticate_parameters_merged.keys()])
            )
            raise ConnectionError(
                "Unable to connect with OpenID Connect: not supported on this server."
            )

        mandatory_headers = ["redirecturi", "authority", "clientid"]
        missing_headers = []
        bearer_parameters_raw = authenticate_parameters_merged["bearer"]
        if bearer_parameters_raw is None:
            bearer_parameters = CaseInsensitiveOrderedDict()
        else:
            bearer_parameters = CaseInsensitiveOrderedDict(bearer_parameters_raw)

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

    @staticmethod
    def _fetch_and_parse_well_known(client: httpx.Client, url: str) -> CaseInsensitiveOrderedDict:
        """Fetch and process the required parameters from identity provider's the well-known endpoint.

        Perform a GET request to the endpoint and verify that the required parameters are returned.

        Parameters
        ----------
        client : httpx.Client
            HTTP client used to reach the identity provider (transport settings from IdP session configuration).
        url : str
            URL referencing the OpenID identity provider's well-known endpoint host (``authority``).
        """
        logger.info(f"Fetching configuration information from Identity Provider {url}")
        if not url.endswith("/"):
            url += "/"
        well_known_endpoint = urllib.parse.urljoin(url, ".well-known/openid-configuration")
        authority_response = client.get(well_known_endpoint)

        logger.debug("Received configuration:")
        payload = authority_response.json()
        if not isinstance(payload, dict):
            raise ConnectionError(
                "Unable to connect with OpenID Connect: well-known document was not a JSON object."
            )
        oidc_configuration = CaseInsensitiveOrderedDict(payload)

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
        transport_configuration: TransportConfiguration,
    ) -> TransportConfiguration:
        """Override user-provided ``Accept`` and ``Content-Type`` headers.

        Required to ensure correct response from the OpenID identity provider.

        Parameters
        ----------
        transport_configuration : TransportConfiguration
            Configuration options for connection to the OpenID identity provider.
        """
        if transport_configuration["headers"] is not None:
            headers = transport_configuration["headers"]
            headers["accept"] = "application/json"
            headers["content-type"] = "application/x-www-form-urlencoded;charset=UTF-8"
        return transport_configuration

    def _add_api_audience_if_set(self) -> None:
        """Set the ``ApiAudience`` header on connection to the API.

        Only add if provided by the OpenID identity provider. This is mainly required for Auth0.
        """
        if "apiAudience" not in self._authenticate_parameters:
            return
        mi_headers = self._api_session_configuration["headers"]
        mi_headers["audience"] = self._authenticate_parameters["apiAudience"]
        idp_headers = self._idp_session_configuration["headers"]
        idp_headers["audience"] = self._authenticate_parameters["apiAudience"]
