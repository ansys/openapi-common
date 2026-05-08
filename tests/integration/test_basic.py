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

import pytest

from ansys.openapi.common import (
    ApiClientFactory,
    ApiConnectionException,
    AuthenticationScheme,
    SessionConfiguration,
)

from .async_integration import run_with_factory_and_async_client
from .common import (
    CustomResponseHeaders,
    TEST_PASS,
    TEST_URL,
    TEST_USER,
    model_endpoint_integration_expectations,
    patch_model_integration_expectations,
)
from .fixture_apps import run_basic_auth_server
from .server_utils import spawn_uvicorn_subprocess, spawn_uvicorn_with_optional_context


class BasicTestCases:
    def test_can_connect(self, auth_mode):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        try:
            _ = client_factory.with_credentials(
                TEST_USER, TEST_PASS, authentication_scheme=auth_mode
            ).connect()
        finally:
            client_factory.close()

    def test_invalid_user_return_401(self, auth_mode):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        try:
            with pytest.raises(ApiConnectionException) as exception_info:
                _ = client_factory.with_credentials(
                    "eve", "password", authentication_scheme=auth_mode
                ).connect()
            resp = exception_info.value.response
            reason_text = getattr(resp, "reason_phrase", None) or getattr(resp, "reason", "")
            assert resp.status_code == 401
            assert "Unauthorized" in reason_text
        finally:
            client_factory.close()

    def test_get_health_returns_200_ok(self, auth_mode):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        try:
            client = client_factory.with_credentials(
                TEST_USER, TEST_PASS, authentication_scheme=auth_mode
            ).connect()
            resp = client.request("GET", TEST_URL + "/test_api")
            assert resp.status_code == 200
            assert "OK" in resp.text
        finally:
            client_factory.close()

    def test_patch_model(self, auth_mode):
        from .. import models

        ctx = patch_model_integration_expectations()
        expected = ctx["expected"]

        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        try:
            client = client_factory.with_credentials(
                TEST_USER, TEST_PASS, authentication_scheme=auth_mode
            ).connect()
            client.setup_client(models)
            response = client.call_api(
                ctx["resource_path"],
                ctx["http_method"],
                path_params=ctx["path_params"],
                body=ctx["upload_data"],
                response_type=ctx["response_type"],
                _return_http_data_only=True,
            )
            assert response == expected
        finally:
            client_factory.close()

    @pytest.mark.parametrize(
        "http_method",
        ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
    )
    def test_model_resource_http_verbs(self, auth_mode, http_method):
        from .. import models

        ctx = model_endpoint_integration_expectations(http_method)
        expected = ctx["expected"]

        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        try:
            client = client_factory.with_credentials(
                TEST_USER, TEST_PASS, authentication_scheme=auth_mode
            ).connect()
            client.setup_client(models)
            response = client.call_api(
                ctx["resource_path"],
                ctx["http_method"],
                path_params=ctx["path_params"],
                body=ctx["body"],
                response_type=ctx["response_type"],
                _return_http_data_only=True,
            )
            assert response == expected
        finally:
            client_factory.close()


class AsyncBasicTestCases:
    """HTTP via :class:`~ansys.openapi.common.AsyncApiClient` after sync :meth:`ApiClientFactory.connect`."""

    def test_can_connect(self, auth_mode):
        async def body(api):
            resp = await api.arequest("GET", TEST_URL + "/test_api")
            assert resp.status_code == 200

        run_with_factory_and_async_client(
            TEST_URL,
            lambda f: f.with_credentials(
                TEST_USER, TEST_PASS, authentication_scheme=auth_mode
            ).connect(),
            body,
        )

    def test_get_health_returns_200_ok(self, auth_mode):
        async def body(api):
            resp = await api.arequest("GET", TEST_URL + "/test_api")
            assert resp.status_code == 200
            assert "OK" in resp.text

        run_with_factory_and_async_client(
            TEST_URL,
            lambda f: f.with_credentials(
                TEST_USER, TEST_PASS, authentication_scheme=auth_mode
            ).connect(),
            body,
        )

    def test_patch_model(self, auth_mode):
        from .. import models

        ctx = patch_model_integration_expectations()
        expected = ctx["expected"]

        async def body(api):
            api.setup_client(models)
            response = await api.acall_api(
                ctx["resource_path"],
                ctx["http_method"],
                path_params=ctx["path_params"],
                body=ctx["upload_data"],
                response_type=ctx["response_type"],
                _return_http_data_only=True,
            )
            assert response == expected

        run_with_factory_and_async_client(
            TEST_URL,
            lambda f: f.with_credentials(
                TEST_USER, TEST_PASS, authentication_scheme=auth_mode
            ).connect(),
            body,
        )

    @pytest.mark.parametrize(
        "http_method",
        ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
    )
    def test_model_resource_http_verbs(self, auth_mode, http_method):
        from .. import models

        ctx = model_endpoint_integration_expectations(http_method)
        expected = ctx["expected"]

        async def body(api):
            api.setup_client(models)
            response = await api.acall_api(
                ctx["resource_path"],
                ctx["http_method"],
                path_params=ctx["path_params"],
                body=ctx["body"],
                response_type=ctx["response_type"],
                _return_http_data_only=True,
            )
            assert response == expected

        run_with_factory_and_async_client(
            TEST_URL,
            lambda f: f.with_credentials(
                TEST_USER, TEST_PASS, authentication_scheme=auth_mode
            ).connect(),
            body,
        )


@pytest.mark.parametrize("auth_mode", [AuthenticationScheme.AUTO, AuthenticationScheme.BASIC])
class TestBasic(BasicTestCases):
    @pytest.fixture(autouse=True)
    def server(self):
        with spawn_uvicorn_subprocess(run_basic_auth_server):
            yield


@pytest.mark.parametrize("auth_mode", [AuthenticationScheme.AUTO, AuthenticationScheme.BASIC])
class TestBasicAsync(AsyncBasicTestCases):
    @pytest.fixture(autouse=True)
    def server(self):
        with spawn_uvicorn_subprocess(run_basic_auth_server):
            yield


@pytest.mark.parametrize("auth_mode", [AuthenticationScheme.BASIC])
class TestBasicWrongHeader(BasicTestCases):
    @pytest.fixture(autouse=True)
    def server(self):
        with spawn_uvicorn_with_optional_context(
            run_basic_auth_server,
            CustomResponseHeaders("www-authenticate", 'Bearer realm="example"'),
        ):
            yield


@pytest.mark.parametrize("auth_mode", [AuthenticationScheme.BASIC])
class TestBasicWrongHeaderAsync(AsyncBasicTestCases):
    @pytest.fixture(autouse=True)
    def server(self):
        with spawn_uvicorn_with_optional_context(
            run_basic_auth_server,
            CustomResponseHeaders("www-authenticate", 'Bearer realm="example"'),
        ):
            yield


@pytest.mark.parametrize("auth_mode", [AuthenticationScheme.BASIC])
class TestBasicMissingHeader(BasicTestCases):
    @pytest.fixture(autouse=True)
    def server(self):
        with spawn_uvicorn_with_optional_context(
            run_basic_auth_server,
            CustomResponseHeaders("www-authenticate", None),
        ):
            yield


@pytest.mark.parametrize("auth_mode", [AuthenticationScheme.BASIC])
class TestBasicMissingHeaderAsync(AsyncBasicTestCases):
    @pytest.fixture(autouse=True)
    def server(self):
        with spawn_uvicorn_with_optional_context(
            run_basic_auth_server,
            CustomResponseHeaders("www-authenticate", None),
        ):
            yield
