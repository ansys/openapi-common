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

"""FastAPI apps and uvicorn targets shared by integration tests (picklable for ``multiprocessing``)."""

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from starlette.responses import Response
import uvicorn

from tests.integration.common import (
    TEST_MODEL_ID,
    TEST_PORT,
    CustomResponseHeaders,
    ExampleModelPyd,
    return_model,
    validate_user_basic,
    validate_user_principal,
)

# --- Basic auth (tests.integration.test_basic*) ---

BASIC_AUTH_APP = FastAPI()
_basic_security = HTTPBasic()


@BASIC_AUTH_APP.middleware("http")
async def _basic_modify_response_headers(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 401:
        CustomResponseHeaders.modify_response_headers(response)
    return response


@BASIC_AUTH_APP.patch("/models/{model_id}")
async def _basic_patch_model(
    model_id: str,
    example_model: ExampleModelPyd,
    credentials: HTTPBasicCredentials = Depends(_basic_security),
):
    validate_user_basic(credentials)
    return return_model(model_id, example_model)


@BASIC_AUTH_APP.get("/models/{model_id}")
async def _basic_get_model(
    model_id: str, credentials: HTTPBasicCredentials = Depends(_basic_security)
):
    validate_user_basic(credentials)
    return return_model(model_id, ExampleModelPyd())


@BASIC_AUTH_APP.post("/models")
async def _basic_post_model(
    example_model: ExampleModelPyd,
    credentials: HTTPBasicCredentials = Depends(_basic_security),
):
    validate_user_basic(credentials)
    return return_model(TEST_MODEL_ID, example_model)


@BASIC_AUTH_APP.put("/models/{model_id}")
async def _basic_put_model(
    model_id: str,
    example_model: ExampleModelPyd,
    credentials: HTTPBasicCredentials = Depends(_basic_security),
):
    validate_user_basic(credentials)
    return return_model(model_id, example_model)


@BASIC_AUTH_APP.delete("/models/{model_id}")
async def _basic_delete_model(
    model_id: str, credentials: HTTPBasicCredentials = Depends(_basic_security)
):
    validate_user_basic(credentials)
    return return_model(model_id, ExampleModelPyd())


@BASIC_AUTH_APP.head("/models/{model_id}")
async def _basic_head_model(
    model_id: str, credentials: HTTPBasicCredentials = Depends(_basic_security)
):
    validate_user_basic(credentials)
    if model_id != TEST_MODEL_ID:
        raise HTTPException(status_code=404, detail="Model not found")
    return Response(status_code=200)


@BASIC_AUTH_APP.options("/models/{model_id}")
async def _basic_options_model(
    model_id: str, credentials: HTTPBasicCredentials = Depends(_basic_security)
):
    validate_user_basic(credentials)
    if model_id != TEST_MODEL_ID:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"allowed_methods": "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS"}


@BASIC_AUTH_APP.get("/test_api")
async def _basic_get_test_api(credentials: HTTPBasicCredentials = Depends(_basic_security)):
    validate_user_basic(credentials)
    return {"msg": "OK"}


@BASIC_AUTH_APP.get("/")
async def _basic_get_none(credentials: HTTPBasicCredentials = Depends(_basic_security)):
    validate_user_basic(credentials)
    return None


def run_basic_auth_server() -> None:
    uvicorn.run(BASIC_AUTH_APP, port=TEST_PORT)


# --- Anonymous (tests.integration.test_anonymous*) ---

ANONYMOUS_APP = FastAPI()


@ANONYMOUS_APP.patch("/models/{model_id}")
async def _anon_patch_model(model_id: str, example_model: ExampleModelPyd):
    return return_model(model_id, example_model)


@ANONYMOUS_APP.get("/models/{model_id}")
async def _anon_get_model(model_id: str):
    return return_model(model_id, ExampleModelPyd())


@ANONYMOUS_APP.post("/models")
async def _anon_post_model(example_model: ExampleModelPyd):
    return return_model(TEST_MODEL_ID, example_model)


@ANONYMOUS_APP.put("/models/{model_id}")
async def _anon_put_model(model_id: str, example_model: ExampleModelPyd):
    return return_model(model_id, example_model)


@ANONYMOUS_APP.delete("/models/{model_id}")
async def _anon_delete_model(model_id: str):
    return return_model(model_id, ExampleModelPyd())


@ANONYMOUS_APP.head("/models/{model_id}")
async def _anon_head_model(model_id: str):
    if model_id != TEST_MODEL_ID:
        raise HTTPException(status_code=404, detail="Model not found")
    return Response(status_code=200)


@ANONYMOUS_APP.options("/models/{model_id}")
async def _anon_options_model(model_id: str):
    if model_id != TEST_MODEL_ID:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"allowed_methods": "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS"}


@ANONYMOUS_APP.get("/test_api")
async def _anon_get_test_api():
    return {"msg": "OK"}


@ANONYMOUS_APP.get("/")
async def _anon_get_none():
    return None


def run_anonymous_server() -> None:
    uvicorn.run(ANONYMOUS_APP, port=TEST_PORT)


# --- Negotiate / Kerberos (tests.integration.test_negotiate*) ---

NEGOTIATE_TEST_URL = f"http://test-server:{TEST_PORT}"
NEGOTIATE_PRINCIPAL = "httpuser@EXAMPLE.COM"

NEGOTIATE_APP = FastAPI()


@NEGOTIATE_APP.middleware("http")
async def _nego_modify_response_headers(request: Request, call_next):
    response = await call_next(request)
    if response.status_code == 401:
        CustomResponseHeaders.modify_response_headers(response)
    return response


@NEGOTIATE_APP.patch("/models/{model_id}")
async def _nego_patch_model(model_id: str, example_model: ExampleModelPyd, request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    return return_model(model_id, example_model)


@NEGOTIATE_APP.get("/models/{model_id}")
async def _nego_get_model(model_id: str, request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    return return_model(model_id, ExampleModelPyd())


@NEGOTIATE_APP.post("/models")
async def _nego_post_model(example_model: ExampleModelPyd, request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    return return_model(TEST_MODEL_ID, example_model)


@NEGOTIATE_APP.put("/models/{model_id}")
async def _nego_put_model(model_id: str, example_model: ExampleModelPyd, request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    return return_model(model_id, example_model)


@NEGOTIATE_APP.delete("/models/{model_id}")
async def _nego_delete_model(model_id: str, request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    return return_model(model_id, ExampleModelPyd())


@NEGOTIATE_APP.head("/models/{model_id}")
async def _nego_head_model(model_id: str, request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    if model_id != TEST_MODEL_ID:
        raise HTTPException(status_code=404, detail="Model not found")
    return Response(status_code=200)


@NEGOTIATE_APP.options("/models/{model_id}")
async def _nego_options_model(model_id: str, request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    if model_id != TEST_MODEL_ID:
        raise HTTPException(status_code=404, detail="Model not found")
    return {"allowed_methods": "GET,POST,PUT,PATCH,DELETE,HEAD,OPTIONS"}


@NEGOTIATE_APP.get("/test_api")
async def _nego_get_test_api(request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    return {"msg": "OK"}


@NEGOTIATE_APP.get("/")
async def _nego_get_none(request: Request):
    validate_user_principal(request, NEGOTIATE_PRINCIPAL)
    return None


def run_negotiate_server() -> None:
    from asgi_gssapi import SPNEGOAuthMiddleware

    authenticated_app = SPNEGOAuthMiddleware(NEGOTIATE_APP, hostname="test-server")
    uvicorn.run(authenticated_app, port=TEST_PORT)
