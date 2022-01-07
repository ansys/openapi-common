from multiprocessing import Process

import pytest
import uvicorn
from fastapi import FastAPI, Depends
from asgi_gssapi import SPNEGOAuthMiddleware
from ansys.openapi.common import (
    ApiClientFactory,
    SessionConfiguration,
    ApiConnectionException,
)
from .integration.common import (
    ExampleModelPyd,
    validate_user_basic,
    TEST_MODEL_ID,
    TEST_PORT,
    TEST_PASS,
    TEST_USER,
)


TEST_URL = f"http://test-server:{TEST_PORT}"

app = FastAPI()
authenticated_app = SPNEGOAuthMiddleware(app)


@app.patch("/models/{model_id}")
async def read_main(model_id: str, example_model: ExampleModelPyd):
    if model_id == TEST_MODEL_ID:
        response = {
            "String": example_model.String or "new_model",
            "Integer": example_model.Integer or 1,
            "ListOfStrings": example_model.ListOfStrings or ["red", "yellow", "green"],
            "Boolean": example_model.Boolean or False,
        }
        return response


@app.get("/test_api")
async def read_main():
    return {"msg": "OK"}


@app.get("/")
async def read_main():
    return None


def run_server():
    uvicorn.run(authenticated_app, port=TEST_PORT)


class TestBasic:
    @pytest.fixture(autouse=True)
    def server(self):
        proc = Process(target=run_server, args=(), daemon=True)
        proc.start()
        yield
        proc.kill()

    def test_can_connect(self):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        _ = client_factory.with_autologon().connect()

    def test_get_health_returns_200_ok(self):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        client = client_factory.with_autologon().connect()

        resp = client.request("GET", TEST_URL + "/test_api")
        assert resp.status_code == 200
        assert "OK" in resp.text

    def test_patch_model(self):
        from .models import ExampleModel

        deserialized_response = ExampleModel(
            string_property="new_model",
            int_property=1,
            list_property=["red", "yellow", "green"],
            bool_property=False,
        )

        resource_path = "/models/ID"
        method = "PATCH"
        path_params = {"ID": TEST_MODEL_ID}

        from .models import ExampleModel

        response_type = ExampleModel

        upload_data = {"ListOfStrings": ["red", "yellow", "green"]}

        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        client = client_factory.with_autologon().connect()

        response = client.call_api(
            resource_path,
            method,
            path_params=path_params,
            body=upload_data,
            response_type=response_type,
            _return_http_data_only=True,
        )
        assert response == deserialized_response
