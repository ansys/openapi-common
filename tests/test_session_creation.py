# Copyright (C) 2022 - 2024 ANSYS, Inc. and/or its affiliates.
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

from functools import wraps
import json
import os
import sys
from urllib.parse import parse_qs

import pytest
import requests
import requests_mock
import requests_ntlm

from ansys.openapi.common import (
    ApiClientFactory,
    ApiConnectionException,
    AuthMode,
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
    "1MTYyMzkwMjJ9.Gm9bqy4CL4_mXKPYrnt2nHGxGM_WaLGpGHrYE_U9uJQ"
)


def test_anonymous():
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=200, reason="OK", text="Connection OK")
        _ = ApiClientFactory(SERVICELAYER_URL).with_anonymous()


@pytest.mark.parametrize(
    ("status_code", "reason_phrase"),
    [(403, "Forbidden"), (404, "Not Found"), (500, "Internal Server Error")],
)
def test_other_status_codes_throw(status_code, reason_phrase):
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=status_code, reason=reason_phrase)
        with pytest.raises(ApiConnectionException) as excinfo:
            _ = ApiClientFactory(SERVICELAYER_URL).with_anonymous()
        assert excinfo.value.response.status_code == status_code
        assert excinfo.value.response.reason == reason_phrase


def test_missing_www_authenticate_throws():
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=401, reason="Unauthorized")
        with pytest.raises(ValueError) as excinfo:
            _ = ApiClientFactory(SERVICELAYER_URL).with_autologon()
        assert "www-authenticate" in str(excinfo.value)


def test_unconfigured_builder_throws():
    with pytest.raises(ValueError) as excinfo:
        _ = ApiClientFactory(SERVICELAYER_URL).connect()

    assert "authentication" in str(excinfo.value)


def test_can_connect_with_basic():
    with requests_mock.Mocker() as m:
        m.get(
            SERVICELAYER_URL,
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="localhost"'},
        )
        m.get(
            SERVICELAYER_URL,
            status_code=200,
            request_headers={"Authorization": "Basic VEVTVF9VU0VSOlBBU1NXT1JE"},
        )
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER", password="PASSWORD"
        )


def test_can_connect_with_pre_emptive_basic():
    with requests_mock.Mocker() as m:
        m.get(
            SERVICELAYER_URL,
            status_code=200,
            request_headers={"Authorization": "Basic VEVTVF9VU0VSOlBBU1NXT1JE"},
        )
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER", password="PASSWORD", auth_mode=AuthMode.BASIC
        )
        assert m.called_once


def test_can_connect_with_basic_and_domain():
    with requests_mock.Mocker() as m:
        m.get(
            SERVICELAYER_URL,
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="localhost"'},
        )
        m.get(
            SERVICELAYER_URL,
            status_code=200,
            request_headers={"Authorization": "Basic RE9NQUlOXFRFU1RfVVNFUjpQQVNTV09SRA=="},
        )
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER", password="PASSWORD", domain="DOMAIN"
        )


def test_can_connect_with_pre_emptive_basic_and_domain():
    with requests_mock.Mocker() as m:
        m.get(
            SERVICELAYER_URL,
            status_code=200,
            request_headers={"Authorization": "Basic RE9NQUlOXFRFU1RfVVNFUjpQQVNTV09SRA=="},
        )
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER", password="PASSWORD", domain="DOMAIN", auth_mode=AuthMode.BASIC
        )
        assert m.called_once


# In Auto mode, the single call is during the initial request to retrieve the header
# In Basic and NTLM modes, the single call is the test request
@pytest.mark.parametrize(
    "auth_mode",
    [
        AuthMode.AUTO,
        AuthMode.BASIC,
        pytest.param(
            AuthMode.NTLM,
            marks=pytest.mark.skipif(sys.platform == "linux", reason="NTLM not supported on Linux"),
        ),
    ],
)
def test_only_called_once_with_basic_when_anonymous_is_ok(auth_mode):
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=200)

        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER",
            password="PASSWORD",
            auth_mode=auth_mode,
        )
        assert m.called_once


@pytest.mark.parametrize(
    "auth_mode",
    [
        AuthMode.AUTO,
        AuthMode.BASIC,
        pytest.param(
            AuthMode.NTLM,
            marks=pytest.mark.skipif(sys.platform == "linux", reason="NTLM not supported on Linux"),
        ),
    ],
)
def test_throws_with_invalid_credentials(auth_mode):
    with requests_mock.Mocker() as m:
        UNAUTHORIZED = "Unauthorized_unique"
        m.get(
            SERVICELAYER_URL,
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="localhost"'},
            reason=UNAUTHORIZED,
        )
        m.get(
            SERVICELAYER_URL,
            status_code=200,
            request_headers={"Authorization": "Basic VEVTVF9VU0VSOlBBU1NXT1JE"},
        )
        with pytest.raises(ApiConnectionException) as exception_info:
            _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
                username="NOT_A_TEST_USER",
                password="PASSWORD",
                auth_mode=auth_mode,
            )
        assert exception_info.value.response.status_code == 401
        assert exception_info.value.response.reason == UNAUTHORIZED


@pytest.mark.parametrize(
    "auth_mode, message",
    [
        (AuthMode.KERBEROS, "AuthMode.KERBEROS is not supported for this method"),
        pytest.param(
            AuthMode.NTLM,
            "AuthMode.NTLM is not supported on Linux",
            marks=pytest.mark.skipif(sys.platform != "Linux", reason="Linux test"),
        ),
        pytest.param(
            AuthMode.NEGOTIATE,
            "AuthMode.NEGOTIATE is not supported on Linux",
            marks=pytest.mark.skipif(sys.platform != "Linux", reason="Linux test"),
        ),
    ],
)
def test_with_credentials_throws_with_invalid_auth_method(auth_mode, message):
    with pytest.raises(ValueError, match=message):
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="NOT_A_TEST_USER",
            password="PASSWORD",
            auth_mode=auth_mode,
        )


def wrap_with_workstation(func):
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        import os

        try:
            current_workstation = os.environ["NETBIOS_COMPUTER_NAME"]
        except KeyError:
            current_workstation = None
        os.environ["NETBIOS_COMPUTER_NAME"] = "TESTWORKSTATION"
        func(self, *args, **kwargs)
        if current_workstation is not None:
            os.environ["NETBIOS_COMPUTER_NAME"] = current_workstation
        else:
            del os.environ["NETBIOS_COMPUTER_NAME"]

    return wrapper


class MockNTLMAuth(requests_ntlm.HttpNtlmAuth):
    def __init__(self, username, password, session=None):
        super().__init__(username, password, session, send_cbt=False)


@pytest.mark.skip(reason="Mock is not working in tox for some reason.")
@pytest.mark.skipif(os.name != "nt", reason="NTLM is not currently supported on linux")
@pytest.mark.parametrize("auth_mode", [AuthMode.AUTO, AuthMode.NTLM])
def test_can_connect_with_ntlm(mocker, auth_mode):
    expect1 = {"Authorization": "NTLM TlRMTVNTUAABAAAAMZCI4gAAAAAoAAAAAAAAACgAAAAGAbEdAAAADw=="}
    response1 = {
        "WWW-Authenticate": "NTLM TlRMTVNTUAACAAAAHgAeADgAAAA1gori1CEifyE0ovkAAAAAAAAAAJgAmABWAAAAC"
        "gBhSgAAAA9UAEUAUwBUAFcATwBSAEsAUwBUAEEAVABJAE8ATgACAB4AVABFAFMAVABXAE8AUgBLAFMAVABBAFQASQB"
        "PAE4AAQAeAFQARQBTAFQAVwBPAFIASwBTAFQAQQBUAEkATwBOAAQAHgBUAEUAUwBUAFcATwBSAEsAUwBUAEEAVABJA"
        "E8ATgADAB4AVABFAFMAVABXAE8AUgBLAFMAVABBAFQASQBPAE4ABwAIADbWHPMoRNcBAAAAAA=="
    }
    expect2 = {
        "Authorization": "NTLM TlRMTVNTUAADAAAAGAAYAGgAAADQANAAgAAAAAAAAABYAAAAEAAQAFgAAAAAAAAAaAAAAAg"
        "ACABQAQAANYKK4gYBsR0AAAAPgNpphHi8APlNXyGtGcP/LUkASQBTAF8AVABlAHMAdAAAAAAAAAAAAAAAAAAAAAAAAAAA"
        "AAAAAADBY98WhVO4ccHK2mJ3PQ+GAQEAAAAAAAA21hzzKETXAd6tvu/erb7vAAAAAAIAHgBUAEUAUwBUAFcATwBSAEsAU"
        "wBUAEEAVABJAE8ATgABAB4AVABFAFMAVABXAE8AUgBLAFMAVABBAFQASQBPAE4ABAAeAFQARQBTAFQAVwBPAFIASwBTAF"
        "QAQQBUAEkATwBOAAMAHgBUAEUAUwBUAFcATwBSAEsAUwBUAEEAVABJAE8ATgAHAAgANtYc8yhE1wEGAAQAAgAAAAAAAAA"
        "AAAAAcTfJ2nPXFQA="
    }

    mocker.patch(
        "os.urandom",
        return_value=b"\xDE\xAD\xBE\xEF\xDE\xAD\xBE\xEF",
    )

    mocker.patch("_session.HttpNtlmAuth", MockNTLMAuth)

    with requests_mock.Mocker() as m:
        m.get(
            url=SERVICELAYER_URL,
            status_code=401,
            headers={"WWW-Authenticate": "NTLM"},
        )
        m.get(
            url=SERVICELAYER_URL,
            status_code=401,
            headers=response1,
            request_headers=expect1,
        )
        m.get(url=SERVICELAYER_URL, status_code=200, request_headers=expect2)

        configuration = SessionConfiguration()
        configuration.verify_ssl = False
        _ = ApiClientFactory(
            SERVICELAYER_URL, session_configuration=configuration
        ).with_credentials(
            username="IIS_Test",
            password="rosebud",
            auth_mode=auth_mode,
        )


@pytest.mark.parametrize("auth_mode", [AuthMode.AUTO, AuthMode.NEGOTIATE])
def test_can_connect_with_negotiate(auth_mode):
    pass


@pytest.mark.parametrize(
    "auth_mode",
    [
        AuthMode.AUTO,
        pytest.param(
            AuthMode.KERBEROS,
            marks=pytest.mark.skipif(
                condition=sys.platform == "win32", reason="Kerberos not supported on Windows"
            ),
        ),
        pytest.param(
            AuthMode.NEGOTIATE,
            marks=pytest.mark.skipif(
                condition=sys.platform == "linux", reason="Negotiate not supported on Linux"
            ),
        ),
    ],
)
def test_only_called_once_with_autologon_when_anonymous_is_ok(auth_mode):
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=200)

        _ = ApiClientFactory(SERVICELAYER_URL).with_autologon(auth_mode=auth_mode)
        assert m.called_once


@pytest.mark.parametrize(
    "auth_mode, message",
    [
        (AuthMode.BASIC, "AuthMode.BASIC is not supported for this method"),
        (AuthMode.NTLM, "AuthMode.NTLM is not supported for this method"),
    ],
)
def test_autologon_throws_with_invalid_auth_mode(auth_mode, message):
    with pytest.raises(ValueError, match=message):
        _ = ApiClientFactory(SERVICELAYER_URL).with_autologon(auth_mode=auth_mode)


@pytest.mark.skipif(condition=sys.platform == "linux", reason="Windows only")
def test_autologon_throws_with_kerberos_auth_mode_windows():
    with pytest.raises(
        ValueError, match="AuthMode.KERBEROS is not supported for this method on Windows"
    ):
        _ = ApiClientFactory(SERVICELAYER_URL).with_autologon(auth_mode=AuthMode.KERBEROS)


@pytest.mark.skipif(condition=sys.platform == "win32", reason="Linux only")
def test_autologon_throws_with_negotiate_auth_mode_windows():
    with pytest.raises(
        ValueError, match="AuthMode.NEGOTIATE is not supported for this method on Linux"
    ):
        _ = ApiClientFactory(SERVICELAYER_URL).with_autologon(auth_mode=AuthMode.NEGOTIATE)


def test_can_connect_with_oidc():
    pass


def test_only_called_once_with_oidc_when_anonymous_is_ok():
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=200)

        _ = ApiClientFactory(SERVICELAYER_URL).with_oidc().authorize()
        assert m.called_once


def test_can_connect_with_oidc_using_token():
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
    token_response = json.dumps(
        {
            "access_token": ACCESS_TOKEN,
            "expires_in": 3600,
            "refresh_token": refresh_token,
        }
    )

    def match_token_request(request):
        if request.text is None:
            return False
        data = parse_qs(request.text)
        return (
            data.get("client_id", "") == [client_id]
            and data.get("grant_type", "") == ["refresh_token"]
            and data.get("refresh_token", "") == [refresh_token]
        )

    with requests_mock.Mocker() as m:
        m.get(
            f"{authority_url}.well-known/openid-configuration",
            status_code=200,
            text=well_known_response,
        )
        m.post(
            f"{authority_url}token",
            status_code=200,
            additional_matcher=match_token_request,
            text=token_response,
        )
        m.get(
            SECURE_SERVICELAYER_URL,
            status_code=401,
            headers={"WWW-Authenticate": authenticate_header},
        )
        m.get(
            SECURE_SERVICELAYER_URL,
            status_code=200,
            request_headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
        )
        session = (
            ApiClientFactory(SECURE_SERVICELAYER_URL)
            .with_oidc()
            .with_token(refresh_token=refresh_token)
            .connect()
        )
        resp = session.rest_client.get(SECURE_SERVICELAYER_URL)
        assert resp.status_code == 200


def test_can_connect_with_oidc_using_token():
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
    token_response = json.dumps(
        {
            "access_token": ACCESS_TOKEN,
            "expires_in": 3600,
            "refresh_token": refresh_token,
        }
    )

    def match_token_request(request):
        if request.text is None:
            return False
        data = parse_qs(request.text)
        return (
            data.get("client_id", "") == [client_id]
            and data.get("grant_type", "") == ["refresh_token"]
            and data.get("refresh_token", "") == [refresh_token]
        )

    with requests_mock.Mocker() as m:
        m.get(
            f"{authority_url}.well-known/openid-configuration",
            status_code=200,
            text=well_known_response,
        )
        m.post(
            f"{authority_url}token",
            status_code=200,
            additional_matcher=match_token_request,
            text=token_response,
        )
        m.get(
            SECURE_SERVICELAYER_URL,
            status_code=401,
            headers={"WWW-Authenticate": authenticate_header},
        )
        m.get(
            SECURE_SERVICELAYER_URL,
            status_code=200,
            request_headers={"Authorization": f"Bearer {ACCESS_TOKEN}"},
        )
        session = (
            ApiClientFactory(SECURE_SERVICELAYER_URL)
            .with_oidc()
            .with_token(refresh_token=refresh_token)
            .connect()
        )
        resp = session.rest_client.get(SECURE_SERVICELAYER_URL)
        assert resp.status_code == 200


def test_neither_basic_nor_ntlm_throws():
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        with pytest.raises(ConnectionError) as exception_info:
            _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
                username="TEST_USER", password="PASSWORD"
            )
        assert "Unable to connect with credentials" in str(exception_info.value)


def test_no_autologon_throws():
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=401, headers={"WWW-Authenticate": "Bearer"})
        with pytest.raises(ConnectionError) as exception_info:
            _ = ApiClientFactory(SERVICELAYER_URL).with_autologon()
        assert "Unable to connect with autologon" in str(exception_info.value)


def test_no_oidc_throws():
    with requests_mock.Mocker() as m:
        m.get(
            SERVICELAYER_URL,
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="localhost"'},
        )
        with pytest.raises(ConnectionError) as exception_info:
            _ = (
                ApiClientFactory(SERVICELAYER_URL)
                .with_oidc()
                .with_token(access_token=ACCESS_TOKEN, refresh_token=REFRESH_TOKEN)
            )
        assert "Unable to connect with OpenID Connect" in str(exception_info.value)


def test_self_signed_throws():
    pass


def test_invalid_initial_response_raises_exception():
    factory = ApiClientFactory(SERVICELAYER_URL)
    with requests_mock.Mocker() as m:
        m.get(
            SERVICELAYER_URL,
            status_code=404,
        )
        resp = requests.get(SERVICELAYER_URL)
    with pytest.raises(ApiConnectionException, match=rf".*{SERVICELAYER_URL}.*404.*"):
        factory._ApiClientFactory__handle_initial_response(resp)
