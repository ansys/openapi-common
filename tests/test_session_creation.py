import json
import os
from functools import wraps

import pytest
import requests_mock
import requests_ntlm
import backoff

from ansys.openapi.common import (
    SessionConfiguration,
    ApiClientFactory,
    ApiConnectionException,
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
        assert excinfo.value.status_code == status_code
        assert excinfo.value.reason_phrase == reason_phrase


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
            request_headers={
                "Authorization": "Basic RE9NQUlOXFRFU1RfVVNFUjpQQVNTV09SRA=="
            },
        )
        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER", password="PASSWORD", domain="DOMAIN"
        )


def test_only_called_once_with_basic_when_anonymous_is_ok():
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=200)

        _ = ApiClientFactory(SERVICELAYER_URL).with_credentials(
            username="TEST_USER", password="PASSWORD"
        )
        assert m.called_once


def test_throws_with_invalid_credentials():
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
                username="NOT_A_TEST_USER", password="PASSWORD"
            )
        assert exception_info.value.status_code == 401
        assert exception_info.value.reason_phrase == UNAUTHORIZED


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
def test_can_connect_with_ntlm(mocker):
    expect1 = {
        "Authorization": "NTLM TlRMTVNTUAABAAAAMZCI4gAAAAAoAAAAAAAAACgAAAAGAbEdAAAADw=="
    }
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
        )


def test_can_connect_with_negotiate():
    pass


def test_only_called_once_with_autologon_when_anonymous_is_ok():
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=200)

        _ = ApiClientFactory(SERVICELAYER_URL).with_autologon()
        assert m.called_once


def test_can_connect_with_oidc():
    pass


def test_only_called_once_with_oidc_when_anonymous_is_ok():
    with requests_mock.Mocker() as m:
        m.get(SERVICELAYER_URL, status_code=200)

        _ = ApiClientFactory(SERVICELAYER_URL).with_oidc().authorize()
        assert m.called_once


@backoff.on_exception(backoff.expo, OSError)
def test_can_connect_with_oidc_using_token():
    redirect_uri = "https://www.example.com/login/"
    authority_url = "https://www.example.com/authority/"
    client_id = "b4e44bfa-6b73-4d6a-9df6-8055216a5836"
    authenticate_header = f'Bearer redirecturi="{redirect_uri}", authority="{authority_url}", clientid="{client_id}"'
    well_known_response = json.dumps(
        {
            "token_endpoint": f"{authority_url}token",
            "authorization_endpoint": f"{authority_url}authorization",
        }
    )
    with requests_mock.Mocker() as m:
        m.get(
            f"{authority_url}.well-known/openid-configuration",
            status_code=200,
            text=well_known_response,
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
            .with_token(access_token=ACCESS_TOKEN, refresh_token="")
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
