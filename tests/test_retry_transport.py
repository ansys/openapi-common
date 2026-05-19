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

import asyncio
from collections.abc import Awaitable, Callable

import httpx
import pytest

from ansys.openapi.common import SessionConfiguration
from ansys.openapi.common._retry_transport import RetryingAsyncHTTPTransport, RetryingHTTPTransport
from ansys.openapi.common._util import (
    create_async_httpx_client_from_session_configuration,
    create_httpx_client_from_session_configuration,
)

_URL = "https://example.test/resource"

# Default retry status set (mirrors ``RetryingHTTPTransport`` / session wiring).
_DEFAULT_RETRYABLE_HTTP_STATUSES = (400, 429, 500, 502, 503, 504)


def _run_session_async_client_test(
    retry_count: int,
    exercise: Callable[[httpx.AsyncClient], Awaitable[None]],
) -> None:
    async def _runner() -> None:
        client = create_async_httpx_client_from_session_configuration(
            SessionConfiguration(retry_count=retry_count)
        )
        try:
            await exercise(client)
        finally:
            await client.aclose()

    asyncio.run(_runner())


# --- Synchronous client (SessionConfiguration + httpx.Client) ----------------


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


def test_transport_error_exhausted_raises(httpx_mock):
    """After ``retry_count`` transport failures, the last error is re-raised."""
    err = httpx.ConnectError("refused")
    httpx_mock.add_exception(err, url=_URL, method="GET")
    httpx_mock.add_exception(err, url=_URL, method="GET")
    httpx_mock.add_exception(err, url=_URL, method="GET")
    with create_httpx_client_from_session_configuration(
        SessionConfiguration(retry_count=3)
    ) as client:
        with pytest.raises(httpx.ConnectError, match="refused"):
            client.get(_URL)
    assert len(httpx_mock.get_requests(url=_URL)) == 3


def test_non_retryable_exception_no_second_request(httpx_mock):
    """Errors outside the retry tuple are not retried."""
    httpx_mock.add_exception(RuntimeError("not a transport retry"), url=_URL, method="GET")
    with create_httpx_client_from_session_configuration(
        SessionConfiguration(retry_count=3)
    ) as client:
        with pytest.raises(RuntimeError, match="not a transport retry"):
            client.get(_URL)
    assert len(httpx_mock.get_requests(url=_URL)) == 1


def test_no_status_retry_for_non_retryable_http_status(httpx_mock):
    """Statuses not in ``retry_status_codes`` return immediately (no extra attempt)."""
    httpx_mock.add_response(url=_URL, method="GET", status_code=404, text="gone")
    with create_httpx_client_from_session_configuration(
        SessionConfiguration(retry_count=3)
    ) as client:
        r = client.get(_URL)
    assert r.status_code == 404
    assert len(httpx_mock.get_requests(url=_URL)) == 1


@pytest.mark.parametrize("retryable_status", _DEFAULT_RETRYABLE_HTTP_STATUSES)
def test_retries_default_status_codes_then_ok(httpx_mock, retryable_status):
    """Each default retry status triggers one retry then succeeds."""
    httpx_mock.add_response(url=_URL, method="GET", status_code=retryable_status)
    httpx_mock.add_response(url=_URL, method="GET", status_code=200, text="ok")
    with create_httpx_client_from_session_configuration(
        SessionConfiguration(retry_count=3)
    ) as client:
        r = client.get(_URL)
    assert r.status_code == 200
    assert r.text == "ok"
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


def test_custom_retry_status_codes_matching_status_retries(httpx_mock):
    """Only statuses listed in ``retry_status_codes`` trigger HTTP retries."""
    url = "https://example.test/custom-retry-502"
    httpx_mock.add_response(url=url, method="GET", status_code=502)
    httpx_mock.add_response(url=url, method="GET", status_code=200, text="ok")
    transport = RetryingHTTPTransport(
        max_attempts=3,
        retry_status_codes=[502],
        verify=True,
    )
    try:
        request = httpx.Request("GET", url)
        response = transport.handle_request(request)
        assert response.status_code == 200
        response.read()
        assert response.text == "ok"
        assert len(httpx_mock.get_requests(url=url)) == 2
    finally:
        transport.close()


def test_custom_retry_status_codes_skips_unlisted_status(httpx_mock):
    """Statuses omitted from ``retry_status_codes`` are returned without retry."""
    url = "https://example.test/custom-no-503-retry"
    httpx_mock.add_response(url=url, method="GET", status_code=503)
    transport = RetryingHTTPTransport(
        max_attempts=3,
        retry_status_codes=[502],
        verify=True,
    )
    try:
        request = httpx.Request("GET", url)
        response = transport.handle_request(request)
        assert response.status_code == 503
        assert len(httpx_mock.get_requests(url=url)) == 1
    finally:
        transport.close()


@pytest.mark.parametrize("http_method", ["GET", "POST"])
def test_retry_http_methods_lowercase_normalized(httpx_mock, http_method):
    """``retry_http_methods`` entries are normalized to upper case for matching."""
    url = f"https://example.test/lowercase-{http_method.lower()}"
    httpx_mock.add_response(url=url, method=http_method, status_code=503)
    httpx_mock.add_response(url=url, method=http_method, status_code=200, text="ok")
    transport = RetryingHTTPTransport(
        max_attempts=3,
        retry_http_methods=[http_method.lower()],
        verify=True,
    )
    try:
        request = httpx.Request(http_method, url)
        response = transport.handle_request(request)
        assert response.status_code == 200
        assert len(httpx_mock.get_requests(url=url)) == 2
    finally:
        transport.close()


# --- Async client (SessionConfiguration + httpx.AsyncClient) -----------------


def test_retries_http_503_then_ok_async(httpx_mock):
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)
    httpx_mock.add_response(url=_URL, method="GET", status_code=200, text="ok")

    async def exercise(client: httpx.AsyncClient) -> None:
        r = await client.get(_URL)
        assert r.status_code == 200
        assert r.text == "ok"

    _run_session_async_client_test(3, exercise)
    assert len(httpx_mock.get_requests(url=_URL)) == 2


def test_retries_stop_after_max_attempts_async(httpx_mock):
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)

    async def exercise(client: httpx.AsyncClient) -> None:
        r = await client.get(_URL)
        assert r.status_code == 503

    _run_session_async_client_test(3, exercise)
    assert len(httpx_mock.get_requests(url=_URL)) == 3


def test_retry_count_one_skips_status_retry_async(httpx_mock):
    httpx_mock.add_response(url=_URL, method="GET", status_code=503)

    async def exercise(client: httpx.AsyncClient) -> None:
        r = await client.get(_URL)
        assert r.status_code == 503

    _run_session_async_client_test(1, exercise)
    assert len(httpx_mock.get_requests(url=_URL)) == 1


def test_retries_connect_error_async(httpx_mock):
    httpx_mock.add_exception(httpx.ConnectError("refused"), url=_URL, method="GET")
    httpx_mock.add_response(url=_URL, method="GET", status_code=200, text="ok")

    async def exercise(client: httpx.AsyncClient) -> None:
        r = await client.get(_URL)
        assert r.status_code == 200
        assert r.text == "ok"

    _run_session_async_client_test(3, exercise)
    assert len(httpx_mock.get_requests(url=_URL)) == 2


def test_transport_error_exhausted_raises_async(httpx_mock):
    err = httpx.ConnectError("refused")
    httpx_mock.add_exception(err, url=_URL, method="GET")
    httpx_mock.add_exception(err, url=_URL, method="GET")
    httpx_mock.add_exception(err, url=_URL, method="GET")

    async def exercise(client: httpx.AsyncClient) -> None:
        with pytest.raises(httpx.ConnectError, match="refused"):
            await client.get(_URL)

    _run_session_async_client_test(3, exercise)
    assert len(httpx_mock.get_requests(url=_URL)) == 3


def test_non_retryable_exception_no_second_request_async(httpx_mock):
    httpx_mock.add_exception(RuntimeError("not a transport retry"), url=_URL, method="GET")

    async def exercise(client: httpx.AsyncClient) -> None:
        with pytest.raises(RuntimeError, match="not a transport retry"):
            await client.get(_URL)

    _run_session_async_client_test(3, exercise)
    assert len(httpx_mock.get_requests(url=_URL)) == 1


def test_no_status_retry_for_non_retryable_http_status_async(httpx_mock):
    httpx_mock.add_response(url=_URL, method="GET", status_code=404, text="gone")

    async def exercise(client: httpx.AsyncClient) -> None:
        r = await client.get(_URL)
        assert r.status_code == 404

    _run_session_async_client_test(3, exercise)
    assert len(httpx_mock.get_requests(url=_URL)) == 1


@pytest.mark.parametrize("retryable_status", _DEFAULT_RETRYABLE_HTTP_STATUSES)
def test_retries_default_status_codes_then_ok_async(httpx_mock, retryable_status):
    httpx_mock.add_response(url=_URL, method="GET", status_code=retryable_status)
    httpx_mock.add_response(url=_URL, method="GET", status_code=200, text="ok")

    async def exercise(client: httpx.AsyncClient) -> None:
        r = await client.get(_URL)
        assert r.status_code == 200
        assert r.text == "ok"

    _run_session_async_client_test(3, exercise)
    assert len(httpx_mock.get_requests(url=_URL)) == 2


def test_status_retry_not_applied_for_disallowed_method_async(httpx_mock):
    """Non-whitelisted methods do not trigger HTTP status retries (async transport)."""
    url = "https://example.test/other-async"
    httpx_mock.add_response(url=url, method="TRACE", status_code=503)

    async def main():
        transport = RetryingAsyncHTTPTransport(
            max_attempts=3,
            retry_http_methods=["GET"],
            verify=True,
        )
        try:
            request = httpx.Request("TRACE", url)
            response = await transport.handle_async_request(request)
            assert response.status_code == 503
        finally:
            await transport.aclose()

    asyncio.run(main())
    assert len(httpx_mock.get_requests(url=url)) == 1


def test_custom_retry_status_codes_matching_status_retries_async(httpx_mock):
    url = "https://example.test/custom-retry-502-async"
    httpx_mock.add_response(url=url, method="GET", status_code=502)
    httpx_mock.add_response(url=url, method="GET", status_code=200, text="ok")

    async def main():
        transport = RetryingAsyncHTTPTransport(
            max_attempts=3,
            retry_status_codes=[502],
            verify=True,
        )
        try:
            request = httpx.Request("GET", url)
            response = await transport.handle_async_request(request)
            assert response.status_code == 200
            await response.aread()
            assert response.text == "ok"
            assert len(httpx_mock.get_requests(url=url)) == 2
        finally:
            await transport.aclose()

    asyncio.run(main())


def test_custom_retry_status_codes_skips_unlisted_status_async(httpx_mock):
    url = "https://example.test/custom-no-503-retry-async"
    httpx_mock.add_response(url=url, method="GET", status_code=503)

    async def main():
        transport = RetryingAsyncHTTPTransport(
            max_attempts=3,
            retry_status_codes=[502],
            verify=True,
        )
        try:
            request = httpx.Request("GET", url)
            response = await transport.handle_async_request(request)
            assert response.status_code == 503
            assert len(httpx_mock.get_requests(url=url)) == 1
        finally:
            await transport.aclose()

    asyncio.run(main())


@pytest.mark.parametrize("http_method", ["GET", "POST"])
def test_retry_http_methods_lowercase_normalized_async(httpx_mock, http_method):
    url = f"https://example.test/lowercase-{http_method.lower()}-async"
    httpx_mock.add_response(url=url, method=http_method, status_code=503)
    httpx_mock.add_response(url=url, method=http_method, status_code=200, text="ok")

    async def main():
        transport = RetryingAsyncHTTPTransport(
            max_attempts=3,
            retry_http_methods=[http_method.lower()],
            verify=True,
        )
        try:
            request = httpx.Request(http_method, url)
            response = await transport.handle_async_request(request)
            assert response.status_code == 200
            assert len(httpx_mock.get_requests(url=url)) == 2
        finally:
            await transport.aclose()

    asyncio.run(main())
