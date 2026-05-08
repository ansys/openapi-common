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

import httpx
import pytest

from ansys.openapi.common import (
    AsyncApiClient,
    SessionConfiguration,
    create_async_httpx_client_from_session_configuration,
)
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
