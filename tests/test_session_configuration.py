import http.cookiejar
import secrets
import tempfile

import pytest
import requests
from requests.utils import CaseInsensitiveDict

from ansys.openapi.common import SessionConfiguration

CLIENT_CERT_PATH = "./client-cert.pem"
CLIENT_CERT_KEY = "5up3rS3c43t!"
CA_CERT_PATH = "./ca-certs.pem"
PROXY_CONFIG = {"https://www.google.com:80": "https://proxy.mycompany.com:8080"}


def test_defaults():
    output = SessionConfiguration().get_configuration_for_requests()
    assert output["cert"] is None
    assert output["verify"]
    assert len(output["cookies"]) == 0
    assert output["proxies"] == {}
    assert output["headers"] == {}
    assert output["max_redirects"] == 10


def test_cert_path_returns_str():
    output = SessionConfiguration(
        client_cert_path=CLIENT_CERT_PATH
    ).get_configuration_for_requests()
    assert output["cert"] == CLIENT_CERT_PATH


def test_cert_path_and_key_returns_tuple():
    output = SessionConfiguration(
        client_cert_path=CLIENT_CERT_PATH, client_cert_key=CLIENT_CERT_KEY
    ).get_configuration_for_requests()
    assert output["cert"] == (CLIENT_CERT_PATH, CLIENT_CERT_KEY)


@pytest.mark.parametrize("verify", [True, False])
def test_verify_returns_valid(verify):
    output = SessionConfiguration(verify_ssl=verify).get_configuration_for_requests()
    assert output["verify"] == verify


def test_verify_with_path_returns_path():
    output = SessionConfiguration(
        cert_store_path=CA_CERT_PATH
    ).get_configuration_for_requests()
    assert output["verify"] == CA_CERT_PATH


@pytest.fixture
def header_test_fixture():
    config = SessionConfiguration()
    config.headers.update({"lower_case": True, "LoWeR_CaSe": True})
    output = config.get_configuration_for_requests()
    yield output["headers"]


@pytest.mark.parametrize("header_key", ["lower_case", "LoWeR_CaSe", "LOWER_CASE"])
def test_headers_are_case_insensitive(header_test_fixture, header_key):
    assert header_key in header_test_fixture
    assert header_test_fixture[header_key]


def test_update_headers_distinct(header_test_fixture):
    assert "upper_case" not in header_test_fixture
    header_test_fixture.update({"UPPER_CASE": True})
    assert "upper_case" in header_test_fixture
    assert header_test_fixture["upper_case"]


def test_update_headers_indistinct(header_test_fixture):
    assert header_test_fixture["lower_case"]
    header_test_fixture.update({"lOWER_cASE": False})
    assert "lower_case" in header_test_fixture
    assert not header_test_fixture["lower_case"]


def test_proxies():
    output = SessionConfiguration(proxies=PROXY_CONFIG).get_configuration_for_requests()
    assert output["proxies"] == PROXY_CONFIG


def test_cookies():
    cookie_jar = http.cookiejar.CookieJar()
    import time

    test_cookie = http.cookiejar.Cookie(
        version=0,
        name="Test Cookie",
        value="131071",
        domain="www.testdomain.com",
        port="443",
        comment="No comment",
        port_specified=True,
        domain_specified=True,
        domain_initial_dot=False,
        path="/test/",
        path_specified=True,
        secure=False,
        discard=False,
        rest={},
        comment_url="",
        expires=int(time.time()) + 3600,
        rfc2109=True,
    )
    cookie_jar.set_cookie(test_cookie)
    output = SessionConfiguration(cookies=cookie_jar).get_configuration_for_requests()
    assert output["cookies"] is not None

    request = requests.Request(
        method="GET",
        url="http://www.testdomain.com:443/test/",
        cookies=output["cookies"],
    )
    prepared_request = request.prepare()
    assert "Cookie" in prepared_request.headers
    assert "131071" in prepared_request.headers["Cookie"]


def test_redirects():
    output = SessionConfiguration(max_redirects=12000).get_configuration_for_requests()
    assert output["max_redirects"] == 12000


class TestDeserialization:
    @pytest.fixture(autouse=True)
    def _test_input_dict(self):
        self.blank_input = {
            "cert": None,
            "verify": None,
            "cookies": None,
            "proxies": None,
            "headers": None,
            "max_redirects": None,
        }

    def test_blank_input_returns_default_object(self):
        configuration_obj = SessionConfiguration.from_dict(self.blank_input)

        assert configuration_obj.verify_ssl
        assert configuration_obj.cert_store_path is None
        assert configuration_obj.client_cert_key is None
        assert configuration_obj.client_cert_path is None
        assert isinstance(configuration_obj.cookies, http.cookiejar.CookieJar)
        assert configuration_obj.cookies._cookies == {}  # noqa
        assert configuration_obj.headers == CaseInsensitiveDict()
        assert configuration_obj.proxies == {}
        assert configuration_obj.max_redirects == 10
        assert configuration_obj.temp_folder_path == tempfile.gettempdir()

    def test_client_cert_tuple_sets_path_and_key(self):
        test_input = self.blank_input
        test_file_name = "/home/testuser/test_cert.pem"
        test_key = secrets.token_hex(32)
        test_input.update({"cert": (test_file_name, test_key)})

        configuration_obj = SessionConfiguration.from_dict(test_input)

        assert configuration_obj.client_cert_path == test_file_name
        assert configuration_obj.client_cert_key == test_key

    def test_client_cert_with_str_sets_path_only(self):
        test_input = self.blank_input
        test_file_name = "/home/testuser/test_cert.pem"
        test_input.update({"cert": test_file_name})

        configuration_obj = SessionConfiguration.from_dict(test_input)

        assert configuration_obj.client_cert_path == test_file_name
        assert configuration_obj.client_cert_key is None

    def test_verify_ssl_with_str_sets_path_to_store(self):
        test_input = self.blank_input
        test_cert_path = "/home/testuser/test_cert.pem"
        test_input.update({"verify": test_cert_path})

        configuration_obj = SessionConfiguration.from_dict(test_input)

        assert configuration_obj.verify_ssl
        assert configuration_obj.cert_store_path == test_cert_path

    def test_verify_ssl_with_bool_sets_verify_flag(self):
        test_input = self.blank_input
        test_input.update({"verify": False})

        configuration_obj = SessionConfiguration.from_dict(test_input)

        assert configuration_obj.verify_ssl is False
