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

import http.cookiejar
import secrets
import tempfile
import time

import httpx
import pytest

from ansys.openapi.common import CaseInsensitiveDict, SessionConfiguration
from ansys.openapi.common._retry_transport import RetryingHTTPTransport
from ansys.openapi.common._session import ApiClientFactory
from ansys.openapi.common._util import (
    TransportConfiguration,
    create_httpx_client_from_session_configuration,
)

CLIENT_CERT_PATH = "./client-cert.pem"
CLIENT_CERT_KEY = "5up3rS3c43t!"
CA_CERT_PATH = "./ca-certs.pem"
PROXY_URL = "https://proxy.mycompany.com:8080"


def test_defaults():
    output = SessionConfiguration().get_transport_configuration()
    assert output["cert"] is None
    assert output["verify"]
    assert len(output["cookies"]) == 0
    assert output["proxy_url"] is None
    assert output["headers"] == {}
    assert output["max_redirects"] == 10


def test_cert_path_returns_str():
    output = SessionConfiguration(client_cert_path=CLIENT_CERT_PATH).get_transport_configuration()
    assert output["cert"] == CLIENT_CERT_PATH


def test_cert_path_and_key_returns_tuple():
    output = SessionConfiguration(
        client_cert_path=CLIENT_CERT_PATH, client_cert_key=CLIENT_CERT_KEY
    ).get_transport_configuration()
    assert output["cert"] == (CLIENT_CERT_PATH, CLIENT_CERT_KEY)


@pytest.mark.parametrize("verify", [True, False])
def test_verify_returns_valid(verify):
    output = SessionConfiguration(verify_ssl=verify).get_transport_configuration()
    assert output["verify"] == verify


def test_verify_with_path_returns_path():
    output = SessionConfiguration(cert_store_path=CA_CERT_PATH).get_transport_configuration()
    assert output["verify"] == CA_CERT_PATH


@pytest.fixture
def header_test_fixture():
    config = SessionConfiguration()
    config.headers.update({"lower_case": True, "LoWeR_CaSe": True})
    output = config.get_transport_configuration()
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


def test_proxy_url():
    output = SessionConfiguration(proxy_url=PROXY_URL).get_transport_configuration()
    assert output["proxy_url"] == PROXY_URL


def test_cookies():
    cookie_jar = http.cookiejar.CookieJar()

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
    output = SessionConfiguration(cookies=cookie_jar).get_transport_configuration()
    assert output["cookies"] is not None

    with httpx.Client(cookies=output["cookies"]) as client:
        req = client.build_request("GET", "http://www.testdomain.com:443/test/")
    assert "cookie" in req.headers
    assert "131071" in req.headers["cookie"]


def test_redirects():
    output = SessionConfiguration(max_redirects=12000).get_transport_configuration()
    assert output["max_redirects"] == 12000


class TestDeserialization:
    @pytest.fixture(autouse=True)
    def _test_input_dict(self):
        self.blank_input = {
            "cert": None,
            "verify": None,
            "cookies": None,
            "proxy_url": None,
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
        assert configuration_obj.proxy_url is None
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

    def test_client_cert_with_int_throws(self):
        test_input = self.blank_input
        test_input.update({"cert": 12})

        with pytest.raises(ValueError) as excinfo:
            _ = SessionConfiguration.from_dict(test_input)

        assert "int" in str(excinfo.value)

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

    def test_verify_ssl_with_int_throws(self):
        test_input = self.blank_input
        test_input.update({"verify": 12})

        with pytest.raises(ValueError) as excinfo:
            _ = SessionConfiguration.from_dict(test_input)

        assert "int" in str(excinfo.value)

    def test_assign_all_values(self):
        test_input: TransportConfiguration = self.blank_input
        test_input["verify"] = CA_CERT_PATH

        cookie_jar = http.cookiejar.CookieJar()
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
        test_input["cookies"] = cookie_jar

        proxy_url = "http://10.10.1.10:3128"
        test_input["proxy_url"] = proxy_url
        header_name = "X-TestHeader"
        header_value = "Foo"
        test_input["headers"] = CaseInsensitiveDict({header_name: header_value})
        test_input["max_redirects"] = 30

        config_object = SessionConfiguration.from_dict(test_input)

        assert config_object.verify_ssl
        assert config_object.cert_store_path == CA_CERT_PATH
        assert config_object.proxy_url == proxy_url
        assert header_name in config_object.headers
        assert config_object.headers[header_name] == header_value
        assert config_object.max_redirects == 30

        assert config_object.cookies is not None

        with httpx.Client(cookies=config_object.cookies) as client:
            req = client.build_request("GET", "http://www.testdomain.com:443/test/")
        assert "cookie" in req.headers
        assert "131071" in req.headers["cookie"]


class TestHttpxClientTransportFromSessionConfiguration:
    """Timeout and retry settings from :class:`SessionConfiguration` apply to ``httpx.Client``."""

    def test_default_timeout_matches_session_configuration(self):
        config = SessionConfiguration()
        with create_httpx_client_from_session_configuration(config) as client:
            assert client.timeout == httpx.Timeout(config.request_timeout)

    def test_custom_request_timeout(self):
        config = SessionConfiguration(request_timeout=17)
        with create_httpx_client_from_session_configuration(config) as client:
            assert client.timeout == httpx.Timeout(17)

    def test_retry_count_maps_to_transport_max_attempts(self):
        config = SessionConfiguration(retry_count=7)
        with create_httpx_client_from_session_configuration(config) as client:
            assert isinstance(client._transport, RetryingHTTPTransport)
            assert client._transport._max_attempts == 7

    def test_proxy_url_requires_mount_scheme_url(self):
        proxy_u = "http://127.0.0.1:8888"
        config = SessionConfiguration(proxy_url=proxy_u)
        with pytest.raises(ValueError, match="mount_scheme_url"):
            create_httpx_client_from_session_configuration(config)

    def test_proxy_url_mount_matches_api_scheme(self):
        proxy_u = "http://127.0.0.1:8888"
        config = SessionConfiguration(proxy_url=proxy_u)
        with create_httpx_client_from_session_configuration(
            config,
            mount_scheme_url="https://api.example/v1/",
        ) as client:
            picked = client._transport_for_url(httpx.URL("https://api.example/resource"))
            assert isinstance(picked, RetryingHTTPTransport)
            assert picked is not client._transport
            plain = client._transport_for_url(httpx.URL("http://other.example/"))
            assert plain is client._transport


class TestWwwAuthenticateHeaderMerging:
    def test_multiple_header_lines_merged(self):
        headers = httpx.Headers(
            [
                ("www-authenticate", "Negotiate"),
                ("www-authenticate", 'Basic realm="example.com"'),
            ]
        )
        response = httpx.Response(401, headers=headers)
        parsed = ApiClientFactory._ApiClientFactory__get_authenticate_header(response)
        assert "negotiate" in parsed
        assert "basic" in parsed
