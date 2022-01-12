import sys
from multiprocessing import Process
from time import sleep

import pytest
from pytest_mock import mocker
import uvicorn
from fastapi import FastAPI, HTTPException
from starlette.requests import Request

from ansys.openapi.common import (
    ApiClientFactory,
    SessionConfiguration, ApiConnectionException,
)
from .integration.common import (
    fastapi_test_app,
    TEST_MODEL_ID,
    TEST_PORT,
    ExampleModelPyd,
    return_model,
    validate_user_principal,
)

pytestmark = pytest.mark.kerberos

TEST_URL = f"http://test-server:{TEST_PORT}"

custom_test_app = FastAPI()


@custom_test_app.patch("/models/{model_id}")
async def patch_model(
        model_id: str,
        example_model: ExampleModelPyd,
        request: Request
):
    validate_user_principal(request)
    return return_model(model_id, example_model)


@custom_test_app.get("/test_api")
async def get_test_api(request: Request):
    validate_user_principal(request)
    return {"msg": "OK"}


@custom_test_app.get("/")
async def get_none(request: Request):
    validate_user_principal(request)
    return None


def run_server():
    from asgi_gssapi import SPNEGOAuthMiddleware
    authenticated_app = SPNEGOAuthMiddleware(fastapi_test_app, hostname="test-server")
    uvicorn.run(authenticated_app, port=TEST_PORT)


@pytest.mark.skipif(
    sys.platform == "win32", reason="No portable KDC is available at present"
)
class TestNegotiate:
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


@pytest.mark.skipif(
    sys.platform == "win32", reason="No portable KDC is available at present"
)
class TestNegotiateFailures:
    @pytest.fixture(autouse=True)
    def server(self):
        proc = Process(target=run_server, args=(), daemon=True)
        proc.start()
        yield
        proc.terminate()
        while proc.is_alive():
            sleep(1)

    def test_bad_principal_returns_403(self, mocker):
        mocker.patch(__name__ + '.integration.common.get_valid_principal', return_value='otheruser@EXAMPLE.COM')
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        with pytest.raises(ApiConnectionException) as excinfo:
            _ = client_factory.with_autologon().connect()
        assert excinfo.value.status_code == 403
        assert excinfo.value.reason_phrase == "Unauthorized"
