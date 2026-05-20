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

import base64
from contextlib import nullcontext
import json
import os
import sys
from urllib.parse import parse_qs

import httpx
import pytest

from ansys.openapi.common import (
    ApiClientFactory,
    ApiConnectionException,
    AuthenticationScheme,
    AuthenticationWarning,
    SessionConfiguration,
)

SERVICELAYER_URL = "http://localhost/mi_servicelayer"
SECURE_SERVICELAYER_URL = "https://localhost/mi_servicelayer"
ACCESS_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2"
    "MjM5MDIyfQ.SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV_adQssw5c"
)
REFRESH_TOKEN = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyMzQ1Njc4OTAxIiwibmFtZSI6IkphbmUgU21pdGgiLCJpYXQiOjE"
    "5MTYyMzkwMjJ9.Gm9bqy4CL4_mXKPYrnt2nHGxGM_WaLGpGHrYE_U9uJQ"
)

# NTLM pytest-httpx: assert message *types* (1 negotiate / 3 auth), not exact blobs. Windows SSPI puts
# workstation/version in Type-1; that is not stable across machines. os.urandom is still patched where
# pyspnego uses it
_NTLM_PATCHED_URANDOM = b"\xde\xad\xbe\xef\xde\xad\xbe\xef"
_NTLM_CANNED_CHALLENGE_WWW = (
    "NTLM TlRMTVNTUAACAAAAHgAeADgAAAA1gori1CEifyE0ovkAAAAAAAAAAJgAmABWAAAAC"
    "gBhSgAAAA9UAEUAUwBUAFcATwBSAEsAUwBUAEEAVABJAE8ATgACAB4AVABFAFMAVABXAE8AUgBLAFMAVABBAFQASQB"
    "PAE4AAQAeAFQARQBTAFQAVwBPAFIASwBTAFQAQQBUAEkATwBOAAQAHgBUAEUAUwBUAFcATwBSAEsAUwBUAEEAVABJA"
    "E8ATgADAB4AVABFAFMAVABXAE8AUgBLAFMAVABBAFQASQBPAE4ABwAIADbWHPMoRNcBAAAAAA=="
)
_NTLM_CANNED_CHALLENGE_HEADERS = {"www-authenticate": _NTLM_CANNED_CHALLENGE_WWW}


def _ntlm_message_type(request: httpx.Request) -> int | None:
    """Return NTLM message type (1 negotiate, 2 challenge, 3 authenticate) or ``None``."""
    auth = request.headers.get("Authorization")
    if not auth or not auth.startswith("NTLM "):
        return None
    try:
        raw = base64.b64decode(auth[5:].strip(), validate=True)
    except (ValueError, base64.binascii.Error):
        return None
    if len(raw) < 12:
        return None
    return int.from_bytes(raw[8:12], "little")


def _ntlm_mock_handshake_connect(request: httpx.Request) -> httpx.Response:
    """Drive NTLM against :class:`httpx_ntlm.HttpNtlmAuth` (every leg yields an unauthenticated request first)."""
    t = _ntlm_message_type(request)
    if t is None:
        return httpx.Response(401, headers={"www-authenticate": "NTLM"})
    if t == 1:
        return httpx.Response(401, headers=_NTLM_CANNED_CHALLENGE_HEADERS)
    if t == 3:
        return httpx.Response(200)
    pytest.fail(f"Unexpected NTLM message type {t} in connect mock")


def _ntlm_backend_available() -> bool:
    """False when ``httpx_ntlm`` cannot load (e.g. Windows without MIT Kerberos / spnego chain)."""
    if os.name != "nt":
        return True
    try:
        from httpx_ntlm import HttpNtlmAuth  # noqa: F401

        return True
    except OSError:
        return False


def _response_reason(response):
    """Reason phrase from an ``httpx.Response``."""
    return getattr(response, "reason_phrase", getattr(response, "reason", ""))


def test_anonymous(httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL, method="GET", status_code=200, text="Connection OK"
    )
    _ = ApiClientFactory(SERVICELAYER_URL).with_anonymous()


@pytest.mark.parametrize(
    ("status_code", "reason_phrase"),
    [(403, "Forbidden"), (404, "Not Found"), (500, "Internal Server Error")],
)
def test_anonymous_raises_for_error_status_other_than_401(status_code, reason_phrase, httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=status_code,
        is_reusable=True,
    )
    with pytest.raises(ApiConnectionException) as excinfo:
        _ = ApiClientFactory(SERVICELAYER_URL).with_anonymous()
    assert excinfo.value.response.status_code == status_code
    assert _response_reason(excinfo.value.response) == reason_phrase


def test_autologon_raises_when_401_has_no_www_authenticate(httpx_mock):
    httpx_mock.add_response(url=SERVICELAYER_URL, method="GET", status_code=401)
    with pytest.raises(ValueError) as excinfo:
        _ = ApiClientFactory(SERVICELAYER_URL).with_autologon()
    assert "www-authenticate" in str(excinfo.value)


def test_unconfigured_builder_throws():
    with pytest.raises(ValueError) as excinfo:
        _ = ApiClientFactory(SERVICELAYER_URL).connect()

    assert "authentication" in str(excinfo.value)


def test_can_connect_with_basic(httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=401,
        headers={"www-authenticate": 'Basic realm="localhost"'},
    )
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=200,
        match_headers={"Authorization": "Basic VEVTVF9VU0VSOlBBU1NXT1JE"},
    )
    _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
        username="TEST_USER", password="PASSWORD"
    )


def test_can_connect_with_pre_emptive_basic(httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=200,
        match_headers={"Authorization": "Basic VEVTVF9VU0VSOlBBU1NXT1JE"},
    )
    _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
        username="TEST_USER",
        password="PASSWORD",
        authentication_scheme=AuthenticationScheme.BASIC,
    )
    assert len(httpx_mock.get_requests(url=SERVICELAYER_URL)) == 1


def test_can_connect_with_basic_and_domain(httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=401,
        headers={"www-authenticate": 'Basic realm="localhost"'},
    )
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=200,
        match_headers={"Authorization": "Basic RE9NQUlOXFRFU1RfVVNFUjpQQVNTV09SRA=="},
    )
    _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
        username="TEST_USER", password="PASSWORD", domain="DOMAIN"
    )


def test_can_connect_with_pre_emptive_basic_and_domain(httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=200,
        match_headers={"Authorization": "Basic RE9NQUlOXFRFU1RfVVNFUjpQQVNTV09SRA=="},
    )
    _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
        username="TEST_USER",
        password="PASSWORD",
        domain="DOMAIN",
        authentication_scheme=AuthenticationScheme.BASIC,
    )
    assert len(httpx_mock.get_requests(url=SERVICELAYER_URL)) == 1


# With credentials: if the server accepts anonymous access (200), the factory warns and should only
# hit the API once (AUTO: probe only; BASIC/NTLM: single connection test).
@pytest.mark.parametrize(
    ["auth_mode", "expect_warning"],
    [
        (
            AuthenticationScheme.AUTO,
            pytest.warns(AuthenticationWarning, match="Continuing without credentials"),
        ),
        (AuthenticationScheme.BASIC, nullcontext()),
        pytest.param(
            AuthenticationScheme.NTLM,
            nullcontext(),
            marks=pytest.mark.skipif(
                sys.platform != "win32" or not _ntlm_backend_available(),
                reason="NTLM requires Windows and a working httpx_ntlm/spnego stack (e.g. MIT Kerberos on Windows)",
            ),
        ),
    ],
)
def test_with_credentials_single_request_when_anonymous_allowed(
    auth_mode, expect_warning, httpx_mock
):
    httpx_mock.add_response(url=SERVICELAYER_URL, method="GET", status_code=200)
    with expect_warning:
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER",
            password="PASSWORD",
            authentication_scheme=auth_mode,
        )
    assert len(httpx_mock.get_requests(url=SERVICELAYER_URL)) == 1


@pytest.mark.parametrize(
    "auth_mode",
    [
        AuthenticationScheme.AUTO,
        AuthenticationScheme.BASIC,
        pytest.param(
            AuthenticationScheme.NTLM,
            marks=pytest.mark.skipif(
                sys.platform != "win32" or not _ntlm_backend_available(),
                reason="NTLM requires Windows and a working httpx_ntlm/spnego stack (e.g. MIT Kerberos on Windows)",
            ),
        ),
    ],
)
def test_with_credentials_raises_when_server_rejects_connection_probe(
    auth_mode, httpx_mock, mocker
):
    UNAUTHORIZED = "Unauthorized_unique"

    def unauthorized_response() -> httpx.Response:
        return httpx.Response(
            401,
            extensions={"reason_phrase": UNAUTHORIZED.encode("ascii")},
        )

    if auth_mode == AuthenticationScheme.NTLM:
        mocker.patch("os.urandom", return_value=_NTLM_PATCHED_URANDOM)

        def _ntlm_mock_handshake_invalid(request: httpx.Request) -> httpx.Response:
            t = _ntlm_message_type(request)
            if t is None:
                return httpx.Response(401, headers={"www-authenticate": "NTLM"})
            if t == 1:
                return httpx.Response(401, headers=_NTLM_CANNED_CHALLENGE_HEADERS)
            if t == 3:
                return unauthorized_response()
            pytest.fail(f"Unexpected NTLM message type {t} in invalid-credentials mock")

        httpx_mock.add_callback(
            _ntlm_mock_handshake_invalid, url=SERVICELAYER_URL, method="GET", is_reusable=True
        )
    else:
        if auth_mode == AuthenticationScheme.AUTO:
            httpx_mock.add_response(
                url=SERVICELAYER_URL,
                method="GET",
                status_code=401,
                headers={"www-authenticate": 'Basic realm="localhost"'},
            )
        httpx_mock.add_callback(
            lambda request: unauthorized_response(),
            url=SERVICELAYER_URL,
            method="GET",
            is_reusable=True,
        )
    with pytest.raises(ApiConnectionException) as exception_info:
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="NOT_A_TEST_USER",
            password="PASSWORD",
            authentication_scheme=auth_mode,
        )
    assert exception_info.value.response.status_code == 401
    assert _response_reason(exception_info.value.response) == UNAUTHORIZED


@pytest.mark.skipif(sys.platform != "linux", reason="NTLM only not supported on Linux")
def test_with_credentials_ntlm_raises_on_linux():
    with pytest.raises(ValueError, match="AuthenticationScheme.NTLM is not supported on Linux"):
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="NOT_A_TEST_USER",
            password="PASSWORD",
            authentication_scheme=AuthenticationScheme.NTLM,
        )


@pytest.mark.skipif(os.name != "nt", reason="NTLM is not currently supported on linux")
@pytest.mark.parametrize("auth_mode", [AuthenticationScheme.AUTO, AuthenticationScheme.NTLM])
def test_can_connect_with_ntlm(mocker, auth_mode, httpx_mock):
    """Handshake is mocked with a fixed Type-2 challenge; Type-1/3 handling does not depend on exact SSPI blobs."""
    mocker.patch("os.urandom", return_value=_NTLM_PATCHED_URANDOM)
    httpx_mock.add_callback(
        _ntlm_mock_handshake_connect, url=SERVICELAYER_URL, method="GET", is_reusable=True
    )

    configuration = SessionConfiguration()
    configuration.verify_ssl = False
    _ = ApiClientFactory(SERVICELAYER_URL, session_configuration=configuration).with_credentials(
        username="IIS_Test",
        password="rosebud",
        authentication_scheme=auth_mode,
    )


def test_can_connect_with_negotiate():
    pytest.skip("Not implemented.")


def test_only_called_once_with_autologon_when_anonymous_is_ok(httpx_mock):
    httpx_mock.add_response(url=SERVICELAYER_URL, method="GET", status_code=200)
    with pytest.warns(AuthenticationWarning, match="Continuing without credentials"):
        _ = ApiClientFactory(SERVICELAYER_URL).with_autologon()
    assert len(httpx_mock.get_requests(url=SERVICELAYER_URL)) == 1


def test_can_connect_with_oidc():
    pytest.skip("Not implemented.")


def test_oidc_probe_uses_factory_session_headers_only(httpx_mock):
    """Application headers on the resource server must come from the factory SessionConfiguration."""
    redirect_uri = "https://www.example.com/login/"
    authority_url = "https://www.example.com/authority/"
    authenticate_header = (
        f'Bearer redirecturi="{redirect_uri}", authority="{authority_url}", '
        'clientid="b4e44bfa-6b73-4d6a-9df6-8055216a5836"'
    )
    seen: list[str | None] = []

    def probe(request: httpx.Request) -> httpx.Response:
        seen.append(request.headers.get("X-GrantaApplicationName"))
        return httpx.Response(401, headers={"www-authenticate": authenticate_header})

    httpx_mock.add_callback(probe, url=SECURE_SERVICELAYER_URL, method="GET")
    httpx_mock.add_response(
        url=f"{authority_url}.well-known/openid-configuration",
        method="GET",
        json={
            "token_endpoint": f"{authority_url}token",
            "authorization_endpoint": f"{authority_url}authorization",
        },
    )

    main_cfg = SessionConfiguration(headers={"X-GrantaApplicationName": "FromApiSession"})
    idp_cfg = SessionConfiguration(headers={"X-GrantaApplicationName": "FromIdpSession"})
    _ = ApiClientFactory(
        SECURE_SERVICELAYER_URL,
        session_configuration=main_cfg,
    ).with_oidc(idp_session_configuration=idp_cfg)
    assert seen == ["FromApiSession"]


def test_only_called_once_with_oidc_when_anonymous_is_ok(httpx_mock):
    httpx_mock.add_response(url=SERVICELAYER_URL, method="GET", status_code=200)
    with pytest.warns(AuthenticationWarning, match="Continuing without credentials"):
        _ = ApiClientFactory(SERVICELAYER_URL).with_oidc().authorize()
    assert len(httpx_mock.get_requests(url=SERVICELAYER_URL)) == 1


def test_can_connect_with_oidc_using_refresh_token(httpx_mock):
    redirect_uri = "https://www.example.com/login/"
    authority_url = "https://www.example.com/authority/"
    client_id = "b4e44bfa-6b73-4d6a-9df6-8055216a5836"
    refresh_token = "RrRNWQCQok6sXRn8eAGY4QXus1zq8fk9ZfDN-BeWEmUes"
    authenticate_header = (
        f'Bearer redirecturi="{redirect_uri}", authority="{authority_url}", clientid="{client_id}"'
    )
    well_known_response = json.dumps(
        {
            "token_endpoint": f"{authority_url}token",
            "authorization_endpoint": f"{authority_url}authorization",
        }
    )

    httpx_mock.add_response(
        url=SECURE_SERVICELAYER_URL,
        method="GET",
        status_code=401,
        headers={"www-authenticate": authenticate_header},
    )
    httpx_mock.add_response(
        url=f"{authority_url}.well-known/openid-configuration",
        method="GET",
        text=well_known_response,
    )

    def token_ok(request: httpx.Request) -> httpx.Response:
        if request.content is None:
            return httpx.Response(400)
        data = parse_qs(request.content.decode())
        if not (
            data.get("client_id", "") == [client_id]
            and data.get("grant_type", "") == ["refresh_token"]
            and data.get("refresh_token", "") == [refresh_token]
        ):
            return httpx.Response(400)
        return httpx.Response(
            200,
            json={
                "access_token": ACCESS_TOKEN,
                "expires_in": 3600,
                "refresh_token": refresh_token,
            },
        )

    httpx_mock.add_callback(token_ok, url=f"{authority_url}token", method="POST")
    httpx_mock.add_response(
        url=SECURE_SERVICELAYER_URL,
        method="GET",
        status_code=200,
        match_headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
    )
    session = (
        ApiClientFactory(SECURE_SERVICELAYER_URL)
        .with_oidc()
        .with_token(refresh_token=refresh_token)
        .connect()
    )
    resp = session.rest_client.get(SECURE_SERVICELAYER_URL)
    assert resp.status_code == 200


def _oidc_connect_succeeds_with_provided_access_token(httpx_mock) -> None:
    """Exercise OIDC when the API session is built with a pre-provisioned access token (no token POST)."""
    redirect_uri = "https://www.example.com/login/"
    authority_url = "https://www.example.com/authority/"
    client_id = "b4e44bfa-6b73-4d6a-9df6-8055216a5836"
    access_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUsImlhdCI6MTUxNjIzOTAyMn0.KMUFsIDTnFmyG3nMiGM6H9FNFUROf3wh7SmqJp-QV30"
    well_known_response = json.dumps(
        {
            "token_endpoint": f"{authority_url}token",
            "authorization_endpoint": f"{authority_url}authorization",
        }
    )
    authenticate_header = (
        f'Bearer redirecturi="{redirect_uri}", authority="{authority_url}", clientid="{client_id}"'
    )

    httpx_mock.add_response(
        url=SECURE_SERVICELAYER_URL,
        method="GET",
        status_code=401,
        headers={"www-authenticate": authenticate_header},
    )

    httpx_mock.add_response(
        url=f"{authority_url}.well-known/openid-configuration",
        method="GET",
        text=well_known_response,
    )
    httpx_mock.add_response(
        url=SECURE_SERVICELAYER_URL,
        method="GET",
        status_code=200,
        match_headers={"Authorization": f"Bearer {access_token}"},
    )
    session = (
        ApiClientFactory(SECURE_SERVICELAYER_URL)
        .with_oidc()
        .with_access_token(access_token=access_token)
        .connect()
    )
    resp = session.rest_client.get(SECURE_SERVICELAYER_URL)
    assert resp.status_code == 200


def test_can_connect_with_oidc_using_token(httpx_mock):
    """Connect via OIDC when an access token is supplied (:meth:`.OIDCSessionBuilder.with_access_token`).

    Complements :func:`test_can_connect_with_oidc_using_refresh_token`, which uses ``with_token`` and the
    token endpoint.
    """
    _oidc_connect_succeeds_with_provided_access_token(httpx_mock)


def test_with_credentials_raises_when_server_offers_only_bearer(httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=401,
        headers={"www-authenticate": "Bearer"},
    )
    with pytest.raises(ConnectionError) as exception_info:
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER", password="PASSWORD"
        )
    assert "Unable to connect with credentials" in str(exception_info.value)


def test_autologon_raises_when_server_offers_only_bearer(httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=401,
        headers={"www-authenticate": "Bearer"},
    )
    with pytest.raises(ConnectionError) as exception_info:
        _ = ApiClientFactory(SERVICELAYER_URL).with_autologon()
    assert "Unable to connect with autologon" in str(exception_info.value)


def test_oidc_raises_when_server_offers_only_basic(httpx_mock):
    httpx_mock.add_response(
        url=SERVICELAYER_URL,
        method="GET",
        status_code=401,
        headers={"www-authenticate": 'Basic realm="localhost"'},
    )
    with pytest.raises(ConnectionError) as exception_info:
        _ = (
            ApiClientFactory(SERVICELAYER_URL)
            .with_oidc()
            .with_token(access_token=ACCESS_TOKEN, refresh_token=REFRESH_TOKEN)
        )
    assert "Unable to connect with OpenID Connect" in str(exception_info.value)


def test_self_signed_throws():
    pytest.skip("Not implemented.")


def test_handle_initial_response_raises_for_non_401_error():
    factory = ApiClientFactory(SERVICELAYER_URL)
    resp = httpx.Response(404, request=httpx.Request("GET", SERVICELAYER_URL))
    with pytest.raises(ApiConnectionException, match=rf".*{SERVICELAYER_URL}.*404.*"):
        factory._ApiClientFactory__handle_initial_response(resp)
