from multiprocessing import Process
from time import sleep

from fastapi import Depends, FastAPI
from fastapi.security import HTTPBasic, HTTPBasicCredentials
import pytest
import uvicorn

from ansys.openapi.common import ApiClientFactory, ApiConnectionException, SessionConfiguration

from .integration.common import (
    TEST_MODEL_ID,
    TEST_PASS,
    TEST_PORT,
    TEST_URL,
    TEST_USER,
    ExampleModelPyd,
    return_model,
    validate_user_basic,
)

custom_test_app = FastAPI()
security = HTTPBasic()


@custom_test_app.patch("/models/{model_id}")
async def patch_model(
    model_id: str,
    example_model: ExampleModelPyd,
    credentials: HTTPBasicCredentials = Depends(security),
):
    validate_user_basic(credentials)
    return return_model(model_id, example_model)


@custom_test_app.get("/test_api")
async def get_test_api(credentials: HTTPBasicCredentials = Depends(security)):
    validate_user_basic(credentials)
    return {"msg": "OK"}


@custom_test_app.get("/")
async def get_none(credentials: HTTPBasicCredentials = Depends(security)):
    validate_user_basic(credentials)
    return None


def run_server():
    uvicorn.run(custom_test_app, port=TEST_PORT)


class TestBasic:
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
        _ = client_factory.with_credentials(TEST_USER, TEST_PASS).connect()

    def test_invalid_user_return_401(self):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        with pytest.raises(ApiConnectionException) as exception_info:
            _ = client_factory.with_credentials("eve", "password").connect()
        assert exception_info.value.response.status_code == 401
        assert "Unauthorized" in exception_info.value.response.reason

    def test_get_health_returns_200_ok(self):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        client = client_factory.with_credentials(TEST_USER, TEST_PASS).connect()

        resp = client.request("GET", TEST_URL + "/test_api")
        assert resp.status_code == 200
        assert "OK" in resp.text

    def test_patch_model(self):
        from . import models

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
        client = client_factory.with_credentials(TEST_USER, TEST_PASS).connect()
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
