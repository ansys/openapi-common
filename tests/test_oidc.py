import json

import pytest
import requests
import requests_mock
from unittest.mock import Mock
from covertable import make

from ansys.grantami.common._oidc import OIDCSessionFactory

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
    response = requests.Response()
    response.url = "http://www.example.com"
    response.encoding = "utf-8"
    response.status_code = 401
    response.reason = "Unauthorized"
    yield response


def try_parse_and_assert_failed(response):
    with pytest.raises(ConnectionError) as exception_info:
        _ = OIDCSessionFactory.parse_unauthorized_header(response)
    assert "Unable to connect with OpenID Connect" in str(exception_info.value)
    return exception_info


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


def test_valid_header_returns_correct_values(authenticate_parsing_fixture):
    response = authenticate_parsing_fixture
    pairs = ["=".join([k, '"{}"'.format(v)]) for k, v in REQUIRED_HEADERS.items()]
    response.headers["WWW-Authenticate"] = "Bearer {0}".format(", ".join(pairs))
    parsed_header = OIDCSessionFactory.parse_unauthorized_header(response)
    assert all(parsed_header[k] == v for k, v in REQUIRED_HEADERS.items())


def test_valid_well_known_parsed_correctly():
    response = json.dumps(WELL_KNOWN_PARAMETERS)
    identity_provider_url = "http://www.example.com/"
    with requests_mock.Mocker() as requests_mocker:
        requests_mocker.get(
            "{}.well-known/openid-configuration".format(identity_provider_url),
            status_code=200,
            text=response,
        )
        mock_factory = Mock()
        mock_factory._initial_session = requests.Session()
        mock_factory._idp_requests_configuration = {}
        mock_factory._mi_requests_configuration = {}
        output = OIDCSessionFactory._fetch_and_parse_well_known(
            mock_factory, identity_provider_url
        )
        for k, v in WELL_KNOWN_PARAMETERS.items():
            assert output[k] == v
            assert output[k.upper()] == v


@pytest.mark.parametrize("missing_parameter", WELL_KNOWN_PARAMETERS.keys())
def test_missing_well_known_parameters_throws(missing_parameter):
    parameters = WELL_KNOWN_PARAMETERS.copy()
    del parameters[missing_parameter]
    response = json.dumps(parameters)
    identity_provider_url = "http://www.example.com/"
    with requests_mock.Mocker() as requests_mocker:
        requests_mocker.get(
            "{}.well-known/openid-configuration".format(identity_provider_url),
            status_code=200,
            text=response,
        )
        mock_factory = Mock()
        mock_factory._initial_session = requests.Session()
        mock_factory._idp_requests_configuration = {}
        mock_factory._mi_requests_configuration = {}
        with pytest.raises(ConnectionError) as exception_info:
            _ = OIDCSessionFactory._fetch_and_parse_well_known(
                mock_factory, identity_provider_url
            )
        assert "Unable to connect with OpenID Connect" in str(exception_info.value)
        assert missing_parameter in str(exception_info.value)


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
    assert (
        response["headers"]["content-type"]
        == "application/x-www-form-urlencoded;charset=UTF-8"
    )


def test_override_idp_configuration_with_no_headers_does_nothing():
    configuration = {
        "headers": None,
        "verify": False,
        "proxies": {"www.example.com", "proxy.example.com"},
    }
    response = OIDCSessionFactory._override_idp_header(configuration)
    assert response == configuration


@pytest.mark.parametrize(
    "access_token, refresh_token",
    make(
        [
            [None, "dGhpcyBpcyBhIHRva2VuLCBob25lc3Qh"],
            [None, "dGhpcyBpcyBhIHRva2VuLCBob25lc3Qh"],
        ]
    ),
)
def test_setting_tokens_sets_tokens(access_token, refresh_token):
    mock_factory = Mock()
    session = OIDCSessionFactory.with_token(mock_factory, access_token, refresh_token)
    if access_token:
        assert "access_token" in session.token
        assert session.token["access_token"] == access_token
    if refresh_token:
        assert session._client.refresh_token == refresh_token


def test_setting_timeout_works():
    mock_factory = Mock()
    OIDCSessionFactory.login_timeout.__set__(mock_factory, 12)
    assert mock_factory._login_timeout == 12


@pytest.mark.parametrize("invalid_data", ["foo", 2 + 3j, b"bytestring"])
def test_setting_timeout_with_invalid_data_throws(invalid_data):
    mock_factory = Mock()
    with pytest.raises(TypeError):
        OIDCSessionFactory.login_timeout.__set__(mock_factory, invalid_data)
