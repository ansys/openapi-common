# Copyright (C) 2022 - 2024 ANSYS, Inc. and/or its affiliates.
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

import os
import secrets
from typing import List, Optional

from fastapi import HTTPException, Response, status
from fastapi.security import HTTPBasicCredentials
from pydantic import BaseModel
from starlette.requests import Request

TEST_MODEL_ID = "37630523-deac-44b4-b920-b150ff8a2308"
TEST_PORT = 27768
TEST_URL = f"http://localhost:{TEST_PORT}"
TEST_USER = "api_user"
TEST_PASS = "rosebud"


def validate_user_principal(request: Request, valid_principal: str):
    scope = request.scope
    try:
        principal = scope["gssapi"]["principal"]
        if principal == valid_principal:
            return
        else:
            raise HTTPException(status_code=403, detail="Forbidden")
    except KeyError:
        raise HTTPException(status_code=401, detail="Unauthorized")


def validate_user_basic(credentials: HTTPBasicCredentials) -> None:
    correct_username = secrets.compare_digest(credentials.username, TEST_USER)
    correct_password = secrets.compare_digest(credentials.password, TEST_PASS)
    if not (correct_username and correct_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Basic"},
        )


class ExampleModelPyd(BaseModel):
    String: Optional[str] = None
    Integer: Optional[int] = None
    ListOfStrings: Optional[List[str]] = None
    Boolean: Optional[bool] = None


def return_model(model_id: str, example_model: ExampleModelPyd):
    if model_id == TEST_MODEL_ID:
        response = {
            "String": example_model.String or "new_model",
            "Integer": example_model.Integer or 1,
            "ListOfStrings": example_model.ListOfStrings or ["red", "yellow", "green"],
            "Boolean": example_model.Boolean or False,
        }
        return response
    else:
        raise HTTPException(status_code=404, detail="Model not found")


class CustomResponseHeaders:
    """
    Context manager to manage creating and cleaning up of environment variables that
    describe how to modify response headers in FastAPI middleware.

    Written to support the use case for testing missing or incomplete
    www-authenticate headers, where a server may support Basic authentication
    but not advertise it.

    Parameters
    ----------
    name : str
        The name of the header to be modified.
    value : str, optional
        The value the header should be set to. If this argument is omitted or provided
        as an empty string, the header will be deleted in the response.
    """

    HEADER_ENVIRON_ROOT = "OPENAPI_COMMON_INT_TEST_HEADER_"

    def __init__(self, name: str, value: Optional[str]) -> None:
        self._environ_name = f"{self.HEADER_ENVIRON_ROOT}{name}"
        self._value = value if value is not None else ""

    def __enter__(self) -> None:
        os.environ[self._environ_name] = self._value

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        del os.environ[self._environ_name]

    @classmethod
    def modify_response_headers(cls, response: Response) -> None:
        """
        Apply the header changes captured via this context manager.

        This method translates the requested header changes from environment variables
        to a dictionary of headers, and then applies them to the response.
        """
        header_changes = {
            env.replace(cls.HEADER_ENVIRON_ROOT, "", 1): value if value else None
            for env, value in os.environ.items()
            if env.startswith(cls.HEADER_ENVIRON_ROOT)
        }
        for header_name, value in header_changes.items():
            if value is None:
                del response.headers[header_name.lower()]
            else:
                response.headers[header_name.lower()] = value
