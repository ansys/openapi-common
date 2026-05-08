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

"""Tests for :class:`~ansys.openapi.common.AsyncApiClient` and async client factory."""

from __future__ import annotations

import asyncio
import json
from types import SimpleNamespace

import httpx
import pytest

from ansys.openapi.common import (
    AsyncApiClient,
    SessionConfiguration,
    create_async_httpx_client_from_session_configuration,
)
from ansys.openapi.common._api_client import _aclose_distinct_httpx_auth_clients
from ansys.openapi.common._util import create_httpx_client_from_session_configuration

TEST_URL = "http://localhost/api/v1.svc"


class _JsonOkTransport(httpx.AsyncBaseTransport):
    """Return JSON 200 for any request."""

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:  # noqa: ARG002
        return httpx.Response(200, content=json.dumps({"message": "hello"}).encode())


def test_async_api_client_acall_api():
    async def run() -> None:
        async with httpx.AsyncClient(transport=_JsonOkTransport()) as session:
            client = AsyncApiClient(session, TEST_URL, SessionConfiguration())
            out = await client.acall_api(
                "/ping",
                "GET",
                response_type="dict(str, str)",
                _return_http_data_only=True,
            )
            assert out == {"message": "hello"}

    asyncio.run(run())


def test_async_api_client_rejects_sync_call_api():
    async def run() -> None:
        async with httpx.AsyncClient(transport=_JsonOkTransport()) as session:
            client = AsyncApiClient(session, TEST_URL, SessionConfiguration())
            with pytest.raises(TypeError, match="acall_api"):
                client.call_api("/x", "GET")

    asyncio.run(run())


def test_async_api_client_rejects_sync_context_manager():
    async def run() -> None:
        async with httpx.AsyncClient(transport=_JsonOkTransport()) as session:
            client = AsyncApiClient(session, TEST_URL, SessionConfiguration())
            with pytest.raises(TypeError, match="async with"):
                with client:
                    pass

    asyncio.run(run())


def test_async_api_client_context_manager_aclose():
    async def run() -> None:
        transport = _JsonOkTransport()
        session = httpx.AsyncClient(transport=transport)
        async with AsyncApiClient(session, TEST_URL, SessionConfiguration()) as client:
            assert client.rest_client is session
        assert session.is_closed

    asyncio.run(run())


def test_create_async_client_copies_sync_state():
    sync = create_httpx_client_from_session_configuration(
        SessionConfiguration(headers={"X-T": "1"}),
    )
    try:
        sync.headers["X-Extra"] = "2"
        async_client = create_async_httpx_client_from_session_configuration(
            SessionConfiguration(),
            sync_client=sync,
        )
        try:
            assert async_client.headers["X-T"] == "1"
            assert async_client.headers["X-Extra"] == "2"
        finally:
            asyncio.run(async_client.aclose())
    finally:
        sync.close()


class _DummyAsyncAuth(httpx.Auth):
    """Separate token client on auth, matching patterns used by ``httpx-auth`` OAuth."""

    def __init__(self, token_client: httpx.AsyncClient) -> None:
        self.client = token_client

    async def async_auth_flow(self, request: httpx.Request):  # noqa: ARG002
        yield request


def test_async_api_client_aclose_disposes_distinct_auth_token_client():
    async def run() -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        inner = httpx.AsyncClient(transport=transport)
        outer = httpx.AsyncClient(transport=transport, auth=_DummyAsyncAuth(inner))
        client = AsyncApiClient(outer, TEST_URL, SessionConfiguration())
        await client.aclose()
        assert inner.is_closed
        assert outer.is_closed

    asyncio.run(run())


def test_aclose_distinct_skips_when_auth_is_none():
    async def run() -> None:
        rest = SimpleNamespace(auth=None)
        await _aclose_distinct_httpx_auth_clients(rest)  # type: ignore[arg-type]

    asyncio.run(run())


def test_aclose_distinct_skips_non_httpx_token_clients():
    async def run() -> None:
        rest = SimpleNamespace(
            auth=SimpleNamespace(authentication_modes=[SimpleNamespace(client="not-a-client")])
        )
        await _aclose_distinct_httpx_auth_clients(rest)  # type: ignore[arg-type]

    asyncio.run(run())


def test_aclose_distinct_closes_distinct_async_token_client():
    async def run() -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        tok = httpx.AsyncClient(transport=transport)
        rest = SimpleNamespace(
            auth=SimpleNamespace(authentication_modes=[SimpleNamespace(client=tok)])
        )
        await _aclose_distinct_httpx_auth_clients(rest)  # type: ignore[arg-type]
        assert tok.is_closed

    asyncio.run(run())


def test_aclose_distinct_closes_distinct_sync_token_client():
    async def run() -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        tok = httpx.Client(transport=transport)
        rest = SimpleNamespace(
            auth=SimpleNamespace(authentication_modes=[SimpleNamespace(client=tok)])
        )
        await _aclose_distinct_httpx_auth_clients(rest)  # type: ignore[arg-type]
        assert tok.is_closed

    asyncio.run(run())


def test_aclose_distinct_skips_nested_client_when_same_as_rest_client():
    async def run() -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        shared = httpx.AsyncClient(transport=transport)
        mode = SimpleNamespace(client=shared)
        # Bypass httpx auth validation; production stacks attach richer auth objects.
        object.__setattr__(
            shared,
            "_auth",
            SimpleNamespace(authentication_modes=[mode]),
        )
        await _aclose_distinct_httpx_auth_clients(shared)
        assert not shared.is_closed
        await shared.aclose()
        assert shared.is_closed

    asyncio.run(run())


def test_aclose_distinct_deduplicates_same_token_client():
    class _CountingAsyncClient(httpx.AsyncClient):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.aclose_calls = 0

        async def aclose(self) -> None:
            self.aclose_calls += 1
            await super().aclose()

    async def run() -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        tok = _CountingAsyncClient(transport=transport)
        modes = [SimpleNamespace(client=tok), SimpleNamespace(client=tok)]
        rest = SimpleNamespace(auth=SimpleNamespace(authentication_modes=modes))
        await _aclose_distinct_httpx_auth_clients(rest)  # type: ignore[arg-type]
        assert tok.aclose_calls == 1
        assert tok.is_closed

    asyncio.run(run())


def test_aclose_distinct_single_auth_object_without_modes_list():
    async def run() -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        tok = httpx.AsyncClient(transport=transport)
        rest = SimpleNamespace(auth=SimpleNamespace(client=tok))
        await _aclose_distinct_httpx_auth_clients(rest)  # type: ignore[arg-type]
        assert tok.is_closed

    asyncio.run(run())


def test_async_api_client_sync_close_raises_type_error():
    async def run() -> None:
        async with httpx.AsyncClient(transport=_JsonOkTransport()) as session:
            client = AsyncApiClient(session, TEST_URL, SessionConfiguration())
            with pytest.raises(TypeError, match="await aclose"):
                client.close()

    asyncio.run(run())


def test_async_api_client_aclose_idempotent():
    async def run() -> None:
        transport = _JsonOkTransport()
        session = httpx.AsyncClient(transport=transport)
        client = AsyncApiClient(session, TEST_URL, SessionConfiguration())
        await client.aclose()
        assert session.is_closed
        await client.aclose()

    asyncio.run(run())


def test_async_api_client_aclose_requires_async_httpx_client():
    async def run() -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        sync_session = httpx.Client(transport=transport)
        try:
            client = AsyncApiClient(sync_session, TEST_URL, SessionConfiguration())
            with pytest.raises(TypeError, match="AsyncApiClient requires an httpx.AsyncClient"):
                await client.aclose()
        finally:
            sync_session.close()

    asyncio.run(run())


def test_arequest_requires_async_httpx_client():
    async def run() -> None:
        transport = httpx.MockTransport(lambda r: httpx.Response(200))
        sync_session = httpx.Client(transport=transport)
        try:
            client = AsyncApiClient(sync_session, TEST_URL, SessionConfiguration())
            with pytest.raises(TypeError, match="AsyncApiClient requires an httpx.AsyncClient"):
                await client.arequest("GET", TEST_URL + "/x")
        finally:
            sync_session.close()

    asyncio.run(run())


def test_arequest_invalid_http_verb():
    async def run() -> None:
        async with httpx.AsyncClient(transport=_JsonOkTransport()) as session:
            client = AsyncApiClient(session, TEST_URL, SessionConfiguration())
            with pytest.raises(ValueError, match="http method must be"):
                await client.arequest("TEAPOT", TEST_URL + "/x")

    asyncio.run(run())


def test_acall_api_invalid_http_verb():
    async def run() -> None:
        async with httpx.AsyncClient(transport=_JsonOkTransport()) as session:
            client = AsyncApiClient(session, TEST_URL, SessionConfiguration())
            with pytest.raises(ValueError, match="http method must be"):
                await client.acall_api("/x", "WABBAJACK", response_type="dict(str, str)")

    asyncio.run(run())
