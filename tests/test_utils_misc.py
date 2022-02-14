import secrets
import threading
import psutil
import time
from multiprocessing import Process

import pytest
import requests

from ansys.openapi.common._util import (
    CaseInsensitiveOrderedDict,
    OIDCCallbackHTTPServer,
)


class TestCaseInsensitiveOrderedDict:
    @pytest.fixture(autouse=True)
    def _example_dict_fixture(self):
        self.example_dict = CaseInsensitiveOrderedDict({"foo": "bar", "BaZ": "qux"})

    def test_get_item(self):
        assert self.example_dict["foo"] == "bar"
        assert self.example_dict["FoO"] == "bar"
        assert self.example_dict["baz"] == "qux"

    def test_set_item(self):
        self.example_dict["FoO"] = "zog"
        assert self.example_dict["foo"] == "zog"

    def test_delete_item(self):
        del self.example_dict["foo"]
        with pytest.raises(KeyError):
            _ = self.example_dict["foo"]
        del self.example_dict["baz"]
        with pytest.raises(KeyError):
            _ = self.example_dict["baz"]

    def test_item_get_method(self):
        assert self.example_dict.get("foo") == "bar"
        assert self.example_dict.get("FoO") == "bar"
        assert self.example_dict.get("baz") == "qux"
        assert self.example_dict.get("grault", None) is None

    def test_setdefault(self):
        assert self.example_dict.setdefault("foo") == "bar"
        assert self.example_dict.setdefault("FoO") == "bar"
        assert self.example_dict.setdefault("gRAuLt", "zog") == "zog"
        assert self.example_dict.setdefault("grault", "ftagn") == "zog"
        assert self.example_dict["grault"] == "zog"

    def test_pop(self):
        assert self.example_dict.pop("foo") == "bar"
        with pytest.raises(KeyError):
            _ = self.example_dict["foo"]
        assert self.example_dict.pop("baz") == "qux"
        with pytest.raises(KeyError):
            _ = self.example_dict["BaZ"]
        assert self.example_dict.pop("grault", "ftagn") == "ftagn"
        default_obj = self.example_dict.pop("spam")
        assert isinstance(default_obj, object)

    def test_update(self):
        self.example_dict.update({"BaZ": "grault", "gRaUlT": "ftagn"})
        assert self.example_dict["baz"] == "grault"
        assert self.example_dict["grault"] == "ftagn"

    def test_contains(self):
        assert "foo" in self.example_dict
        assert "FOo" in self.example_dict
        assert "baz" in self.example_dict
        assert "BaZ" in self.example_dict

    def test_copy(self):
        copied_dict = self.example_dict.copy()
        assert copied_dict == self.example_dict

    def test_from_keys_with_default_value(self):
        new_dict = CaseInsensitiveOrderedDict.fromkeys(("foo", "bar"))
        assert "foo" in new_dict
        assert new_dict["FoO"] is None

    def test_from_keys(self):
        new_dict = CaseInsensitiveOrderedDict.fromkeys(("foo", "bar"), "qux")
        assert "bar" in new_dict
        assert new_dict["BaR"] == "qux"

    def test_repr(self):
        repr = self.example_dict.__repr__()
        dict_from_repr = eval(repr)
        assert dict_from_repr == self.example_dict


def run_server():
    callback_server = OIDCCallbackHTTPServer()
    callback_server.handle_request()


@pytest.fixture(scope="function")
def oidc_callback_server_process():
    # Run the OIDC callback server in a process, and return the process
    # Doesn't perform any cleanup, so p.terminate() must be called by the test
    p = Process(target=run_server, daemon=True)
    p.start()
    # Wait for the process to start up
    time.sleep(5)
    return p


@pytest.fixture(scope="function")
def oidc_callback_server():
    # Run the OIDC callback server in a thread, and return the server
    # Clean up when finished
    callback_server = OIDCCallbackHTTPServer()
    thread = threading.Thread(target=callback_server.handle_request)
    thread.daemon = True
    thread.start()
    yield callback_server
    del callback_server
    del thread


class TestOIDCHTTPServer:
    def test_authorize_returns_200(self, oidc_callback_server_process):
        resp = requests.get("http://localhost:32284")
        oidc_callback_server_process.terminate()

        assert resp.status_code == 200
        assert "Login successful" in resp.text
        assert "Content-Type" in resp.headers
        assert "text/html" in resp.headers["Content-Type"]

    def test_authorize_with_code_parses_code(self, oidc_callback_server):
        test_code = secrets.token_hex(32)
        resp = requests.get(f"http://localhost:32284?code={test_code}")
        assert resp.status_code == 200
        assert test_code in oidc_callback_server.auth_code


def test_oidc_callback_server_port_acquisition_and_release(oidc_callback_server_process):
    # Check that the process is bound to the OIDC callback port
    proc = psutil.Process(oidc_callback_server_process.pid)
    assert any([conn.laddr.port == 32284 for conn in proc.connections()])

    # Send the request that will cause the server to close
    requests.get("http://localhost:32284?code=1234567890")

    # Check that the process is no longer bound to the OIDC callback port
    connections = proc.connections(kind="tcp")
    for conn in connections:
        print(conn.laddr)
    assert all([conn.laddr.port != 32284 for conn in connections])

    oidc_callback_server_process.terminate()
