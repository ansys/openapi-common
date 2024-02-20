from multiprocessing import Process
import sys
from time import sleep

from fastapi import FastAPI
import pytest
from starlette.requests import Request
import uvicorn

from ansys.openapi.common import ApiClientFactory, ApiConnectionException, SessionConfiguration

from .integration.common import (
    TEST_MODEL_ID,
    TEST_PORT,
    ExampleModelPyd,
    return_model,
    validate_user_principal,
)

pytestmark = pytest.mark.kerberos

TEST_URL = f"http://test-server:{TEST_PORT}"
TEST_PRINCIPAL = "httpuser@EXAMPLE.COM"

custom_test_app = FastAPI()


@custom_test_app.patch("/models/{model_id}")
async def patch_model(model_id: str, example_model: ExampleModelPyd, request: Request):
    validate_user_principal(request, TEST_PRINCIPAL)
    return return_model(model_id, example_model)


@custom_test_app.get("/test_api")
async def get_test_api(request: Request):
    validate_user_principal(request, TEST_PRINCIPAL)
    return {"msg": "OK"}


@custom_test_app.get("/")
async def get_none(request: Request):
    validate_user_principal(request, TEST_PRINCIPAL)
    return None


def run_server():
    # Function is only executed if testing in Linux
    from asgi_gssapi import SPNEGOAuthMiddleware

    authenticated_app = SPNEGOAuthMiddleware(custom_test_app, hostname="test-server")
    uvicorn.run(authenticated_app, port=TEST_PORT)


@pytest.mark.skipif(sys.platform == "win32", reason="No portable KDC is available at present")
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
        client = client_factory.with_autologon().connect()
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


@pytest.mark.skipif(sys.platform == "win32", reason="No portable KDC is available at present")
class TestNegotiateFailures:
    @pytest.fixture(autouse=True)
    def server(self):
        # Remove all the routes (a bit drastic)
        custom_test_app.router.routes = []

        @custom_test_app.get("/")
        async def get_forbidden(request: Request):
            validate_user_principal(request, "otheruser@EXAMPLE.COM")
            return None

        proc = Process(target=run_server, args=(), daemon=True)
        proc.start()
        yield
        proc.terminate()
        while proc.is_alive():
            sleep(1)

    def test_bad_principal_returns_403(self):
        client_factory = ApiClientFactory(TEST_URL, SessionConfiguration())
        with pytest.raises(ApiConnectionException) as excinfo:
            _ = client_factory.with_autologon().connect()
        assert excinfo.value.response.status_code == 403
        assert excinfo.value.response.reason == "Forbidden"
