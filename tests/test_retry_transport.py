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

import httpx

from ansys.openapi.common import SessionConfiguration
from ansys.openapi.common._retry_transport import RetryingHTTPTransport
from ansys.openapi.common._util import create_httpx_client_from_session_configuration

_URL = "https://example.test/resource"


def test_retries_http_503_then_ok(httpx_mock):
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)
    httpx_mock.add_response(url=_URL, method="GET", status_code=200, text="ok")
    with create_httpx_client_from_session_configuration(
        SessionConfiguration(retry_count=3)
    ) as client:
        r = client.get(_URL)
    assert r.status_code == 200
    assert r.text == "ok"
    assert len(httpx_mock.get_requests(url=_URL)) == 2


def test_retries_stop_after_max_attempts(httpx_mock):
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)
    with create_httpx_client_from_session_configuration(
        SessionConfiguration(retry_count=3)
    ) as client:
        r = client.get(_URL)
    assert r.status_code == 503
    assert len(httpx_mock.get_requests(url=_URL)) == 3


def test_retry_count_one_skips_status_retry(httpx_mock):
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)
    with create_httpx_client_from_session_configuration(
        SessionConfiguration(retry_count=1)
    ) as client:
        r = client.get(_URL)
    assert r.status_code == 503
    assert len(httpx_mock.get_requests(url=_URL)) == 1


def test_retries_connect_error(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("refused"), url=_URL, method="GET")
    httpx_mock.add_response(url=_URL, method="GET", status_code=200, text="ok")
    with create_httpx_client_from_session_configuration(
        SessionConfiguration(retry_count=3)
    ) as client:
        r = client.get(_URL)
    assert r.status_code == 200
    assert len(httpx_mock.get_requests(url=_URL)) == 2


def test_status_retry_not_applied_for_disallowed_method(httpx_mock):
    """Non-whitelisted methods do not trigger HTTP status retries."""
    url = "https://example.test/other"
    httpx_mock.add_response(url=url, method="TRACE", status_code=503)
    transport = RetryingHTTPTransport(
        max_attempts=3,
        retry_http_methods=["GET"],
        verify=True,
    )
    try:
        request = httpx.Request("TRACE", url)
        response = transport.handle_request(request)
        assert response.status_code == 503
        assert len(httpx_mock.get_requests(url=url)) == 1
    finally:
        transport.close()
