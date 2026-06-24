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
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class OIDCConfiguration:
    """OpenID Connect settings for API authentication.

    When provided on :meth:`~ansys.openapi.common.ApiClientFactory.with_oidc`, the OIDC
    session is configured without contacting the API for a ``401`` response.

    Parameters
    ----------
    client_id : str, optional
        OAuth client identifier. Maps from the ``clientid`` ``WWW-Authenticate`` parameter.
    authority : str, optional
        Identity provider authority URL from a ``401`` response. Used only for legacy
        API-driven discovery when ``well_known_url`` and explicit endpoints are not set.
    authorization_endpoint : str, optional
        Authorization endpoint URL. When set together with ``token_endpoint``,
        the well-known endpoint is not contacted.
    token_endpoint : str, optional
        Token endpoint URL.
    well_known_url : str, optional
        OpenID Provider metadata URL. When provided without explicit endpoints,
        ``authorization_endpoint`` and ``token_endpoint`` are fetched from this URL.
    scopes : list[str], optional
        OAuth scopes to request. Maps from the ``scope`` ``WWW-Authenticate`` parameter.
    api_audience : str, optional
        API audience for Auth0-style providers. Maps from the ``apiAudience``
        ``WWW-Authenticate`` parameter. Omit for Azure AD B2C.
    redirect_uri : str, optional
        Registered redirect URI for the interactive login flow. Maps from the
        ``redirecturi`` ``WWW-Authenticate`` parameter.
    redirect_uri_port : int, optional
        Local port used for the browser redirect when ``redirect_uri`` is not set.
        The default is ``32284``.
    """

    client_id: Optional[str] = None
    authority: Optional[str] = None
    authorization_endpoint: Optional[str] = None
    token_endpoint: Optional[str] = None
    well_known_url: Optional[str] = None
    scopes: Optional[List[str]] = None
    api_audience: Optional[str] = None
    redirect_uri: Optional[str] = None
    redirect_uri_port: int = 32284

    def is_complete(self) -> bool:
        """Return whether enough configuration is present to skip ``401`` discovery."""
        if not self.client_id:
            return False
        if self.authorization_endpoint and self.token_endpoint:
            return True
        return bool(self.well_known_url)

    def has_explicit_endpoints(self) -> bool:
        """Return whether both OAuth endpoints were provided directly."""
        return bool(self.authorization_endpoint and self.token_endpoint)

    def has_partial_endpoints(self) -> bool:
        """Return whether only one OAuth endpoint was provided."""
        return (
            bool(self.authorization_endpoint or self.token_endpoint)
            and not self.has_explicit_endpoints()
        )
