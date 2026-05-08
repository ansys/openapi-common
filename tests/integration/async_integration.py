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

"""Shared helpers for async :class:`~ansys.openapi.common.AsyncApiClient` integration tests."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable

import httpx

from ansys.openapi.common import (
    ApiClient,
    ApiClientFactory,
    AsyncApiClient,
    SessionConfiguration,
    create_async_httpx_client_from_session_configuration,
)


def async_clients_from_sync(sync_api: ApiClient) -> tuple[httpx.AsyncClient, AsyncApiClient]:
    """Build ``httpx.AsyncClient`` + :class:`AsyncApiClient` from a connected sync :class:`ApiClient`."""
    http = create_async_httpx_client_from_session_configuration(
        sync_api.configuration,
        mount_scheme_url=sync_api.api_url,
        sync_client=sync_api.rest_client,
    )
    async_api = AsyncApiClient(http, sync_api.api_url, sync_api.configuration)
    return http, async_api


def run_with_factory_and_async_client(
    base_url: str,
    connect: Callable[[ApiClientFactory], ApiClient],
    body: Callable[[AsyncApiClient], Awaitable[None]],
) -> None:
    """Connect with ``ApiClientFactory``, build async stack from the sync client, run ``await body(api)``."""

    async def main() -> None:
        factory = ApiClientFactory(base_url, SessionConfiguration())
        try:
            sync = connect(factory)
            http, api = async_clients_from_sync(sync)
            try:
                await body(api)
            finally:
                await http.aclose()
        finally:
            factory.close()

    asyncio.run(main())
