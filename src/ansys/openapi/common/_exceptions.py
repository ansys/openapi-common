# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
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

from typing import TYPE_CHECKING, Optional

from requests.structures import CaseInsensitiveDict

if TYPE_CHECKING:
    import requests

    from ansys.openapi.common._base._types import DeserializedType


class ApiConnectionException(Exception):
    """
    Provides the exception to raise when connection to the API server fails.

    For more information about the failure, inspect ``.response``.

    Parameters
    ----------
    response : requests.Response
        Response from the server.
    """

    def __init__(self, response: "requests.Response"):
        exception_message = f"Request url '{response.url}' failed with reason {response.status_code}: {response.reason}."
        if response.text:
            exception_message += f"\n{response.text}"
        super().__init__(exception_message)
        self.response = response

    def __repr__(self) -> str:
        """Printable representation of the object."""
        return f"ApiConnectionException({repr(self.response)})"


class AuthenticationWarning(Warning):
    """Provides the warning to raise when the server connection process completes but does proceed as expected.

    Parameters
    ----------
    message : str
        Cause of the warning and any additional information.
    """

    def __init__(self, message: str) -> None:
        self.message = message

    def __repr__(self) -> str:
        """Printable representation of the object."""
        return f"AuthenticationWarning('{self.message}')"


class ApiException(Exception):
    """
    Provides the exception to raise when the remote server returns an unsuccessful response.

    For more information about the failure, inspect ``.status_code`` and ``.reason_phrase``. If the
    server defines a custom exception model, ``.exception_model`` contains the deserialized response.

    Parameters
    ----------
    status_code : int
        HTTP status code associated with the response.
    reason_phrase : str
        Description of the response provided by the server.
    body : str, optional
        Content of the response provided by the server. The default is ``None``.
    exception_model: ModelBase, optional
        The custom exception model if defined by the server. The default is ``None``.
    headers : CaseInsensitiveDict, optional
        Response headers provided by the server. The default is ``None``.
    """

    status_code: int
    reason_phrase: str
    body: Optional[str]
    exception_model: "DeserializedType"
    headers: Optional[CaseInsensitiveDict]

    def __init__(
        self,
        status_code: int,
        reason_phrase: str,
        body: Optional[str] = None,
        exception_model: "DeserializedType" = None,
        headers: Optional[CaseInsensitiveDict] = None,
    ):
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.body = body
        self.exception_model = exception_model
        self.headers = headers

    @classmethod
    def from_response(
        cls, http_response: "requests.Response", exception_model: "DeserializedType" = None
    ) -> "ApiException":
        """Initialize object from a requests.Response object."""
        new = cls(
            status_code=http_response.status_code,
            reason_phrase=http_response.reason,
            body=http_response.text,
            exception_model=exception_model,
            headers=http_response.headers,
        )
        return new

    def __str__(self) -> str:
        """Printable description of the object."""
        error_message = f"ApiException({self.status_code}, '{self.reason_phrase}')\n"
        if self.headers:
            error_message += f"HTTP response headers: {self.headers}\n"
        if self.body:
            error_message += f"HTTP response body: {self.body}\n"
        return error_message

    def __repr__(self) -> str:
        """Printable representation of the object."""
        return f"ApiException({self.status_code}, '{self.reason_phrase}', '{self.body}')"


class UndefinedObjectWarning(UserWarning):
    """
    Provides a warning for when a model is incompletely described in the OpenAPI definition.

    The data received from the server cannot be fully deserialized, and so the response is provided
    as an un-deserialized dictionary.

    This warning can be safely suppressed if the required detail cannot be added to the OpenAPI
    definition, but in this case the deserialization must be defined manually.
    """
