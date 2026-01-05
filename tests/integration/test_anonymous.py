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

from multiprocessing import Process
from time import sleep

from fastapi import FastAPI
import pytest
import uvicorn

from ansys.openapi.common import ApiClientFactory, AuthenticationWarning, SessionConfiguration
from tests.integration.common import (
    TEST_MODEL_ID,
    TEST_PORT,
    TEST_URL,
    ExampleModelPyd,
    return_model,
)

fastapi_test_app = FastAPI()


@fastapi_test_app.patch("/models/{model_id}")
async def patch_model(model_id: str, example_model: ExampleModelPyd):
    return return_model(model_id, example_model)


@fastapi_test_app.get("/test_api")
async def get_test_api():
    return {"msg": "OK"}


@fastapi_test_app.get("/")
async def get_none():
    return None


def run_server():
    uvicorn.run(fastapi_test_app, port=TEST_PORT)


class TestAnonymous:
    @pytest.fixture(autouse=True)
    def server(self):
        proc = Process(target=run_server, args=(), daemon=True)
        proc.start()
        yield
        proc.terminate()
        while proc.is_alive():
            sleep(1)

    def test_can_connect(self):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        _ = client_factory.with_anonymous().connect()

    def test_get_health_returns_200_ok(self):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        client = client_factory.with_anonymous().connect()

        resp = client.request("GET", TEST_URL + "/test_api")
        assert resp.status_code == 200
        assert "OK" in resp.text

    def test_basic_credentials_raises_warning(self):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        with pytest.warns(AuthenticationWarning, match="anonymous"):
            client = client_factory.with_credentials("TEST_USER", "TEST_PASS").connect()

        resp = client.request("GET", TEST_URL + "/test_api")
        assert resp.status_code == 200
        assert "OK" in resp.text

    def test_patch_model(self):
        from .. import models

        deserialized_response = models.ExampleModel(
            string_property="new_model",
            int_property=1,
            list_property=["red", "yellow", "green"],
            bool_property=False,
        )

        resource_path = "/models/{ID}"
        method = "PATCH"
        path_params = {"ID": TEST_MODEL_ID}

        response_type = "ExampleModel"

        upload_data = {"ListOfStrings": ["red", "yellow", "green"]}

        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        client = client_factory.with_anonymous().connect()
        client.setup_client(models)

        response = client.call_api(
            resource_path,
            method,
            path_params=path_params,
            body=upload_data,
            response_type=response_type,
            _return_http_data_only=True,
        )
        assert response == deserialized_response
