from multiprocessing import Process
from time import sleep

import pytest
import uvicorn

from ansys.openapi.common import (
    ApiClientFactory,
    SessionConfiguration,
    AuthenticationWarning,
)
from .integration.common import fastapi_test_app, TEST_MODEL_ID, TEST_URL, TEST_PORT


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
        client = client_factory.with_anonymous().connect()

        response = client.call_api(
            resource_path,
            method,
            path_params=path_params,
            body=upload_data,
            response_type=response_type,
            _return_http_data_only=True,
        )
        assert response == deserialized_response
