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

import sys

import pytest
from starlette.requests import Request

from ansys.openapi.common import ApiClientFactory, ApiConnectionException, SessionConfiguration

from .async_integration import run_with_factory_and_async_client
from .common import (
    model_endpoint_integration_expectations,
    patch_model_integration_expectations,
    validate_user_principal,
)
from .fixture_apps import NEGOTIATE_APP, NEGOTIATE_TEST_URL, run_negotiate_server
from .server_utils import spawn_uvicorn_subprocess

pytestmark = pytest.mark.kerberos


@pytest.mark.skipif(sys.platform == "win32", reason="No portable KDC is available at present")
class TestNegotiate:
    @pytest.fixture(autouse=True)
    def server(self):
        with spawn_uvicorn_subprocess(run_negotiate_server):
            yield

    def test_can_connect(self):
        client_factory = ApiClientFactory(NEGOTIATE_TEST_URL, SessionConfiguration())
        try:
            _ = client_factory.with_autologon().connect()
        finally:
            client_factory.close()

    def test_get_health_returns_200_ok(self):
        client_factory = ApiClientFactory(NEGOTIATE_TEST_URL, SessionConfiguration())
        try:
            client = client_factory.with_autologon().connect()
            resp = client.request("GET", NEGOTIATE_TEST_URL + "/test_api")
            assert resp.status_code == 200
            assert "OK" in resp.text
        finally:
            client_factory.close()

    def test_patch_model(self):
        from .. import models

        ctx = patch_model_integration_expectations()
        expected = ctx["expected"]

        client_factory = ApiClientFactory(NEGOTIATE_TEST_URL, SessionConfiguration())
        try:
            client = client_factory.with_autologon().connect()
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
    def test_model_resource_http_verbs(self, http_method):
        from .. import models

        ctx = model_endpoint_integration_expectations(http_method)
        expected = ctx["expected"]

        client_factory = ApiClientFactory(NEGOTIATE_TEST_URL, SessionConfiguration())
        try:
            client = client_factory.with_autologon().connect()
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


@pytest.mark.skipif(sys.platform == "win32", reason="No portable KDC is available at present")
class TestNegotiateAsync:
    @pytest.fixture(autouse=True)
    def server(self):
        with spawn_uvicorn_subprocess(run_negotiate_server):
            yield

    def test_can_connect(self):
        async def body(api):
            resp = await api.arequest("GET", NEGOTIATE_TEST_URL + "/test_api")
            assert resp.status_code == 200

        run_with_factory_and_async_client(
            NEGOTIATE_TEST_URL,
            lambda f: f.with_autologon().connect(),
            body,
        )

    def test_get_health_returns_200_ok(self):
        async def body(api):
            resp = await api.arequest("GET", NEGOTIATE_TEST_URL + "/test_api")
            assert resp.status_code == 200
            assert "OK" in resp.text

        run_with_factory_and_async_client(
            NEGOTIATE_TEST_URL,
            lambda f: f.with_autologon().connect(),
            body,
        )

    def test_patch_model(self):
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
            NEGOTIATE_TEST_URL,
            lambda f: f.with_autologon().connect(),
            body,
        )

    @pytest.mark.parametrize(
        "http_method",
        ["GET", "POST", "PUT", "DELETE", "HEAD", "OPTIONS"],
    )
    def test_model_resource_http_verbs(self, http_method):
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
            NEGOTIATE_TEST_URL,
            lambda f: f.with_autologon().connect(),
            body,
        )


@pytest.mark.skipif(sys.platform == "win32", reason="No portable KDC is available at present")
class TestNegotiateFailures:
    @pytest.fixture(autouse=True)
    def server(self):
        original_routes = NEGOTIATE_APP.router.routes
        NEGOTIATE_APP.router.routes = []

        @NEGOTIATE_APP.get("/")
        async def get_forbidden(request: Request):
            validate_user_principal(request, "otheruser@EXAMPLE.COM")
            return None

        with spawn_uvicorn_subprocess(run_negotiate_server):
            yield

        NEGOTIATE_APP.router.routes = original_routes

    @pytest.mark.xfail(
        sys.version_info[:2] == (3, 14),
        reason="Unexpectedly returns 200 with unauthorized user on Python 3.14",
    )
    def test_bad_principal_returns_403(self):
        client_factory = ApiClientFactory(NEGOTIATE_TEST_URL, SessionConfiguration())
        try:
            with pytest.raises(ApiConnectionException) as excinfo:
                _ = client_factory.with_autologon().connect()
            resp = excinfo.value.response
            assert resp.status_code == 403
            reason_text = getattr(resp, "reason_phrase", None) or getattr(resp, "reason", "")
            assert "Forbidden" in reason_text
        finally:
            client_factory.close()
