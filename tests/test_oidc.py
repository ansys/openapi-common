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

import json
from unittest.mock import MagicMock, Mock
from urllib.parse import parse_qs

from covertable import make
import httpx
import pytest
from httpx_auth import OAuth2

from ansys.openapi.common import ApiClientFactory, SessionConfiguration
from ansys.openapi.common._oidc import OIDCSessionFactory

REQUIRED_HEADERS = {
    "clientid": "3acde603-9bb9-48e7-9eaa-c624c4fd40ca",
    "authority": "authority.com",
    "redirecturi": "http://localhost:1729",
}

WELL_KNOWN_PARAMETERS = {
    "token_endpoint": "www.example.com/token",
    "authorization_endpoint": "www.example.com/authorization",
}


@pytest.fixture
def authenticate_parsing_fixture():
    response = httpx.Response(
        401,
        request=httpx.Request("GET", "http://www.example.com"),
    )
    yield response


def try_parse_and_assert_failed(response):
    with pytest.raises(ConnectionError) as exception_info:
        _ = OIDCSessionFactory._parse_unauthorized_header(response)
    assert "Unable to connect with OpenID Connect" in str(exception_info.value)
    return exception_info


def get_session_from_mock_factory_with_refresh_token(refresh_token: str):
    mock_factory = Mock()
    mock_factory._auth = Mock()
    mock_factory._auth.refresh_token = MagicMock(return_value=(0, "token", 1, refresh_token))
    session = OIDCSessionFactory.get_session_with_provided_token(mock_factory, refresh_token)
    return session


def test_no_bearer_throws(authenticate_parsing_fixture):
    response = authenticate_parsing_fixture
    response.headers["WWW-Authenticate"] = 'Basic realm="example.com"'
    exception_info = try_parse_and_assert_failed(response)
    assert "not supported on this server" in str(exception_info.value)


@pytest.mark.parametrize("missing_argument", REQUIRED_HEADERS.keys())
def test_missing_parameters_throws(authenticate_parsing_fixture, missing_argument):
    response = authenticate_parsing_fixture
    pairs = [
        "=".join([k, '"{}"'.format(v)])
        for k, v in REQUIRED_HEADERS.items()
        if k != missing_argument
    ]
    response.headers["WWW-Authenticate"] = "Bearer {0}".format(", ".join(pairs))
    exception_info = try_parse_and_assert_failed(response)
    assert missing_argument in str(exception_info.value)


def test_missing_multiple_parameters_throws(authenticate_parsing_fixture):
    response = authenticate_parsing_fixture
    response.headers["WWW-Authenticate"] = "Bearer"
    exception_info = try_parse_and_assert_failed(response)
    for header_value in REQUIRED_HEADERS:
        assert header_value in str(exception_info.value)


def test_valid_header_returns_correct_values(authenticate_parsing_fixture):
    response = authenticate_parsing_fixture
    pairs = ["=".join([k, '"{}"'.format(v)]) for k, v in REQUIRED_HEADERS.items()]
    response.headers["WWW-Authenticate"] = "Bearer {0}".format(", ".join(pairs))
    parsed_header = OIDCSessionFactory._parse_unauthorized_header(response)
    assert all(parsed_header[k] == v for k, v in REQUIRED_HEADERS.items())


@pytest.mark.parametrize(
    "authority_url",
    ["https://www.example.com/", "https://www.example.com", "https://www.example.com/api/"],
)
def test_valid_well_known_parsed_correctly(httpx_mock, authority_url):
    response = json.dumps(WELL_KNOWN_PARAMETERS)
    if not authority_url.endswith("/"):
        authority_url += "/"
    httpx_mock.add_response(
        url=f"{authority_url}.well-known/openid-configuration",
        method="GET",
        text=response,
    )
    with httpx.Client() as client:
        output = OIDCSessionFactory._fetch_and_parse_well_known(client, authority_url)
    for k, v in WELL_KNOWN_PARAMETERS.items():
        assert output[k] == v
        assert output[k.upper()] == v


@pytest.mark.parametrize("missing_parameter", WELL_KNOWN_PARAMETERS.keys())
def test_missing_well_known_parameters_throws(httpx_mock, missing_parameter):
    parameters = WELL_KNOWN_PARAMETERS.copy()
    del parameters[missing_parameter]
    response = json.dumps(parameters)
    identity_provider_url = "http://www.example.com/"
    httpx_mock.add_response(
        url=f"{identity_provider_url}.well-known/openid-configuration",
        method="GET",
        text=response,
    )
    with httpx.Client() as client:
        with pytest.raises(ConnectionError) as exception_info:
            _ = OIDCSessionFactory._fetch_and_parse_well_known(client, identity_provider_url)
    assert "Unable to connect with OpenID Connect" in str(exception_info.value)
    assert missing_parameter in str(exception_info.value)


def test_multiple_missing_well_known_parameters_throws(httpx_mock):
    parameters = {}
    response = json.dumps(parameters)
    identity_provider_url = "http://www.example.com/"
    httpx_mock.add_response(
        url=f"{identity_provider_url}.well-known/openid-configuration",
        method="GET",
        text=response,
    )
    with httpx.Client() as client:
        with pytest.raises(ConnectionError) as exception_info:
            _ = OIDCSessionFactory._fetch_and_parse_well_known(client, identity_provider_url)
    assert "Unable to connect with OpenID Connect" in str(exception_info.value)
    for header_value in WELL_KNOWN_PARAMETERS:
        assert header_value in str(exception_info.value)


@pytest.mark.parametrize(
    "accept, content_type", make([[None, "application/xml"], [None, "application/xml"]])
)
def test_override_idp_configuration(accept, content_type):
    configuration = {}
    if accept:
        configuration["accept"] = accept
    if content_type:
        configuration["content-type"] = content_type
    response = OIDCSessionFactory._override_idp_header({"headers": configuration})
    assert response["headers"]["accept"] == "application/json"
    assert response["headers"]["content-type"] == "application/x-www-form-urlencoded;charset=UTF-8"


def test_override_idp_configuration_with_no_headers_does_nothing():
    configuration = {
        "headers": None,
        "verify": False,
        "proxy_url": None,
    }
    response = OIDCSessionFactory._override_idp_header(configuration)
    assert response == configuration


def test_add_api_audience_if_set_no_op_when_not_in_authenticate_parameters():
    factory = OIDCSessionFactory.__new__(OIDCSessionFactory)
    factory._authenticate_parameters = dict(REQUIRED_HEADERS)
    api_tc = SessionConfiguration().get_transport_configuration()
    idp_tc = SessionConfiguration().get_transport_configuration()
    factory._api_session_configuration = api_tc
    factory._idp_session_configuration = idp_tc
    OIDCSessionFactory._add_api_audience_if_set(factory)
    assert "audience" not in api_tc["headers"]
    assert "audience" not in idp_tc["headers"]


def test_add_api_audience_if_set_writes_audience_to_api_and_idp_headers():
    factory = OIDCSessionFactory.__new__(OIDCSessionFactory)
    audience = "https://my-api.example.com"
    factory._authenticate_parameters = {**REQUIRED_HEADERS, "apiAudience": audience}
    api_tc = SessionConfiguration().get_transport_configuration()
    idp_tc = SessionConfiguration().get_transport_configuration()
    factory._api_session_configuration = api_tc
    factory._idp_session_configuration = idp_tc
    OIDCSessionFactory._add_api_audience_if_set(factory)
    assert api_tc["headers"]["audience"] == audience
    assert idp_tc["headers"]["audience"] == audience


def test_setting_access_token_with_no_token_throws():
    mock_factory = Mock()
    with pytest.raises(ValueError):
        OIDCSessionFactory.get_session_with_access_token(mock_factory, None)


def test_setting_access_token_sets_access_token():
    example_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiYWRtaW4iOnRydWUsImlhdCI6MTUxNjIzOTAyMn0.KMUFsIDTnFmyG3nMiGM6H9FNFUROf3wh7SmqJp-QV30"
    expected_header = f"Bearer {example_token}"
    mock_factory = Mock()
    mock_factory._authorized_httpx_client = httpx.Client()
    session = OIDCSessionFactory.get_session_with_access_token(
        mock_factory, access_token=example_token
    )

    assert session.headers["Authorization"] == expected_header


def test_setting_refresh_token_with_no_token_throws():
    mock_factory = Mock()
    with pytest.raises(ValueError):
        OIDCSessionFactory.get_session_with_provided_token(mock_factory, None)


def test_setting_refresh_token_sets_refresh_token():
    refresh_token = "dGhpcyBpcyBhIHRva2VuLCBob25lc3Qh"
    OAuth2.token_cache.clear()
    session = get_session_from_mock_factory_with_refresh_token(refresh_token)

    session.auth.refresh_token.assert_called_once_with(refresh_token)
    stored = next(iter(OAuth2.token_cache.tokens.values()))
    assert stored[2] == refresh_token


def test_invalid_refresh_token_throws(httpx_mock):
    api_url = "https://mi-api.com/api"
    authority_url = "https://www.example.com/authority/"
    client_id = "b4e44bfa-6b73-4d6a-9df6-8055216a5836"
    refresh_token = "RrRNWQCQok6sXRn8eAGY4QXus1zq8fk9ZfDN-BeWEmUes"
    redirect_uri = "https://www.example.com/login/"
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
        url=api_url,
        method="GET",
        status_code=401,
        headers={"www-authenticate": authenticate_header},
    )
    httpx_mock.add_response(
        url=f"{authority_url}.well-known/openid-configuration",
        method="GET",
        text=well_known_response,
    )

    def token_exchange_response(request: httpx.Request) -> httpx.Response:
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
            401,
            headers={"WWW-Authenticate": "Bearer error=invalid_token"},
        )

    httpx_mock.add_callback(token_exchange_response, url=f"{authority_url}token", method="POST")

    with pytest.raises(ValueError) as exception_info:
        ApiClientFactory(api_url).with_oidc().with_token(refresh_token=refresh_token)
    assert "refresh token was invalid" in str(exception_info.value)


def test_endpoint_with_refresh_configures_correctly(httpx_mock):
    secure_servicelayer_url = "https://localhost/mi_servicelayer"
    redirect_uri = "https://www.example.com/login/"
    authority_url = "https://www.example.com/authority/"
    client_id = "b4e44bfa-6b73-4d6a-9df6-8055216a5836"
    authenticate_header = (
        f'Bearer redirecturi="{redirect_uri}", authority="{authority_url}", '
        f'clientid="{client_id}", scope="offline_access"'
    )
    well_known_response = json.dumps(
        {
            "token_endpoint": f"{authority_url}token",
            "authorization_endpoint": f"{authority_url}authorization",
        }
    )

    httpx_mock.add_response(
        url=secure_servicelayer_url,
        method="GET",
        status_code=401,
        headers={"www-authenticate": authenticate_header},
    )

    httpx_mock.add_response(
        url=f"{authority_url}.well-known/openid-configuration",
        method="GET",
        text=well_known_response,
    )

    session = ApiClientFactory(secure_servicelayer_url).with_oidc()
    auth = session._session_factory._auth

    assert auth.token_url == f"{authority_url}token"
    assert auth.refresh_data["client_id"] == client_id
