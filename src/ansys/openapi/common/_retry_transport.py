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

"""Synchronous and asynchronous :class:`httpx` transports with retries.

:class:`RetryingHTTPTransport` mirrors historical resilience from
:class:`urllib3.Retry` and ``requests`` HTTP adapters while staying inside the
:class:`httpx` transport layer. :class:`RetryingAsyncHTTPTransport` applies the same
policy for :class:`httpx.AsyncClient`.

Notes
-----
- ``SessionConfiguration.retry_count`` is the maximum number of attempts per logical
  request (including the first try). It maps directly to ``max_attempts`` on these
  transports.

- HTTP status retries: responses whose status is in ``retry_status_codes`` trigger
  another attempt when attempts remain. Default codes include 400 (see migration plan),
  429, 500, 502, 503, and 504.

- Retries apply to ``DELETE``, ``GET``, ``HEAD``, ``OPTIONS``, ``PATCH``, ``POST``,
  and ``PUT``. Retrying ``POST`` when the server returns e.g. 400 before accepting work
  can duplicate side effects; callers must accept that risk on flaky servers (same
  caveat as urllib3-style retries on non-idempotent verbs).

- Transport errors (connection failures, timeouts, low-level read/write errors, and
  :class:`httpx.RemoteProtocolError`) are retried with exponential backoff, with delay
  ``backoff_factor * 2**attempt`` seconds between attempts (urllib3-style shape).

Retry behaviour is not duplicated at the httpcore connection-pool level: leave pool
``retries`` at 0 and control retries only through these transports.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Collection, FrozenSet

import httpx

from ._logger import logger

_DEFAULT_RETRY_STATUSES: FrozenSet[int] = frozenset({400, 429, 500, 502, 503, 504})
_DEFAULT_RETRY_METHODS: FrozenSet[str] = frozenset(
    {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}
)


def _retryable_transport_exceptions() -> tuple[type[BaseException], ...]:
    """Exceptions treated like urllib3 connection/read retries."""
    return (
        httpx.TimeoutException,
        httpx.NetworkError,
        httpx.ProxyError,
        httpx.RemoteProtocolError,
    )


class RetryingHTTPTransport(httpx.HTTPTransport):
    """HTTP transport that retries failed requests up to ``max_attempts`` times."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_factor: float = 0.3,
        retry_status_codes: Collection[int] | None = None,
        retry_http_methods: Collection[str] | None = None,
        **transport_kwargs: Any,
    ) -> None:
        """Create a retrying transport.

        Parameters
        ----------
        max_attempts
            Total attempts per request (minimum 1). Matches ``SessionConfiguration.retry_count``.
        backoff_factor
            Multiplier for exponential backoff between attempts (urllib3-style).
        retry_status_codes
            HTTP statuses that trigger a retry when attempts remain.
        retry_http_methods
            Upper-case method names eligible for HTTP status retries.
        **transport_kwargs
            Forwarded to :class:`httpx.HTTPTransport` (``verify``, ``cert``, ``proxy``, etc.).
        """
        super().__init__(retries=0, **transport_kwargs)
        self._max_attempts = max(1, max_attempts)
        self._backoff_factor = backoff_factor
        self._retry_status_codes = frozenset(retry_status_codes or _DEFAULT_RETRY_STATUSES)
        self._retry_http_methods = frozenset(
            m.upper() for m in (retry_http_methods or _DEFAULT_RETRY_METHODS)
        )
        self._retry_exceptions = _retryable_transport_exceptions()

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        """Dispatch ``request`` with retries for transport errors and configured statuses."""
        method_upper = request.method.upper()
        for attempt in range(self._max_attempts):
            try:
                response = super().handle_request(request)
            except self._retry_exceptions:
                if attempt >= self._max_attempts - 1:
                    raise
                self._sleep_backoff(attempt)
                logger.debug(
                    "Retrying HTTP request after transport error "
                    f"(attempt {attempt + 2}/{self._max_attempts})"
                )
                continue

            if (
                response.status_code in self._retry_status_codes
                and method_upper in self._retry_http_methods
                and attempt < self._max_attempts - 1
            ):
                self._drain_response(response)
                self._sleep_backoff(attempt)
                logger.debug(
                    "Retrying HTTP request after status "
                    f"{response.status_code} (attempt {attempt + 2}/{self._max_attempts})"
                )
                continue

            return response

        raise AssertionError("retry loop fell through")  # pragma: no cover

    def _sleep_backoff(self, attempt_index: int) -> None:
        delay = self._backoff_factor * (2**attempt_index)
        time.sleep(delay)

    @staticmethod
    def _drain_response(response: httpx.Response) -> None:
        try:
            response.read()
        finally:
            response.close()


class RetryingAsyncHTTPTransport(httpx.AsyncHTTPTransport):
    """Async HTTP transport that retries failed requests up to ``max_attempts`` times."""

    def __init__(
        self,
        *,
        max_attempts: int = 3,
        backoff_factor: float = 0.3,
        retry_status_codes: Collection[int] | None = None,
        retry_http_methods: Collection[str] | None = None,
        **transport_kwargs: Any,
    ) -> None:
        """Create a retrying async transport.

        Parameters match :class:`RetryingHTTPTransport`.
        """
        super().__init__(retries=0, **transport_kwargs)
        self._max_attempts = max(1, max_attempts)
        self._backoff_factor = backoff_factor
        self._retry_status_codes = frozenset(retry_status_codes or _DEFAULT_RETRY_STATUSES)
        self._retry_http_methods = frozenset(
            m.upper() for m in (retry_http_methods or _DEFAULT_RETRY_METHODS)
        )
        self._retry_exceptions = _retryable_transport_exceptions()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        """Dispatch ``request`` with retries for transport errors and configured statuses."""
        method_upper = request.method.upper()
        for attempt in range(self._max_attempts):
            try:
                response = await super().handle_async_request(request)
            except self._retry_exceptions:
                if attempt >= self._max_attempts - 1:
                    raise
                await self._sleep_backoff(attempt)
                logger.debug(
                    "Retrying HTTP request after transport error "
                    f"(attempt {attempt + 2}/{self._max_attempts})"
                )
                continue

            if (
                response.status_code in self._retry_status_codes
                and method_upper in self._retry_http_methods
                and attempt < self._max_attempts - 1
            ):
                await self._adrain_response(response)
                await self._sleep_backoff(attempt)
                logger.debug(
                    "Retrying HTTP request after status "
                    f"{response.status_code} (attempt {attempt + 2}/{self._max_attempts})"
                )
                continue

            return response

        raise AssertionError("retry loop fell through")  # pragma: no cover

    async def _sleep_backoff(self, attempt_index: int) -> None:
        delay = self._backoff_factor * (2**attempt_index)
        await asyncio.sleep(delay)

    @staticmethod
    async def _adrain_response(response: httpx.Response) -> None:
        try:
            await response.aread()
        finally:
            await response.aclose()
