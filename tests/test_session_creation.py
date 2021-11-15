import json
from functools import wraps

import pytest
import requests_mock

from ansys.grantami.common import (
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


@pytest.mark.skip(msg="Need to work out how to patch os.urandom correctly. Also need to disable cbt usage.")  # type: ignore[misc]
def test_can_connect_with_ntlm(mocker):
    expect1 = {"Authorization": "NTLM TlRMTVNTUAABAAAAN4II4AAAAAAgAAAAAAAAACAAAAA="}
    response1 = {
        "WWW-Authenticate": "NTLM TlRMTVNTUAACAAAAHgAeADgAAAA1gori1CEifyE0ovkAAAAAAAAAAJgAmABWAAAACgBhSgAAAA9UAEUAUwBUA"
        "FcATwBSAEsAUwBUAEEAVABJAE8ATgACAB4AVABFAFMAVABXAE8AUgBLAFMAVABBAFQASQBPAE4AAQAeAFQARQBTAFQ"
        "AVwBPAFIASwBTAFQAQQBUAEkATwBOAAQAHgBUAEUAUwBUAFcATwBSAEsAUwBUAEEAVABJAE8ATgADAB4AVABFAFMAV"
        "ABXAE8AUgBLAFMAVABBAFQASQBPAE4ABwAIADbWHPMoRNcBAAAAAA=="
    }
    expect2 = {
        "Authorization": "NTLM TlRMTVNTUAADAAAAGAAYAFgAAADwAPAAcAAAAAAAAABgAQAAEAAQAGABAAAeAB4AcAEAAAgACACOAQAANYKK4gAB"
        "BgAAAAAPw38elkNrZcKFdMx/yneDWQAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAACSQFWteoy7KhaGzllQe8OIBAQAAAAAAA"
        "DbWHPMoRNcB3q2+796tvu8AAAAAAgAeAFQARQBTAFQAVwBPAFIASwBTAFQAQQBUAEkATwBOAAEAHgBUAEUAUwBUAFcATw"
        "BSAEsAUwBUAEEAVABJAE8ATgAEAB4AVABFAFMAVABXAE8AUgBLAFMAVABBAFQASQBPAE4AAwAeAFQARQBTAFQAVwBPAFI"
        "ASwBTAFQAQQBUAEkATwBOAAcACAA21hzzKETXAQkAHABIAE8AUwBUAC8AbABvAGMAYQBsAGgAbwBzAHQABgAEAAIAAAAA"
        "AAAAAAAAAEkASQBTAF8AVABlAHMAdABUAEUAUwBUAFcATwBSAEsAUwBUAEEAVABJAE8ATgCbo4V5ivHWOA=="
    }

    # TODO: Mock os.urandom correctly and disable cbt/enable ssl in requests_mock
    # Mock os.urandom since the client challenge is generated for the AUTHENTICATE message with 8 bytes of random
    # date
    mocker.patch(
        "os.urandom",
        return_value=b"\xDE\xAD\xBE\xEF\xDE\xAD\xBE\xEF",
    )
    with requests_mock.Mocker() as m:
        m.get(
            url="http://localhost/test",
            status_code=401,
            headers={"WWW-Authenticate": "NTLM"},
        )
        m.get(
            url="http://localhost/test",
            status_code=401,
            headers=response1,
            request_headers=expect1,
        )
        m.get(url="http://localhost/test", status_code=200, request_headers=expect2)

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


def test_can_connect_with_oidc():
    pass


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
            .with_oidc(access_token=ACCESS_TOKEN)
            .build()
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
            _ = ApiClientFactory(SERVICELAYER_URL).with_oidc(
                access_token=ACCESS_TOKEN, refresh_token=REFRESH_TOKEN
            )
        assert "Unable to connect with OpenID Connect" in str(exception_info.value)


def test_self_signed_throws():
    pass
