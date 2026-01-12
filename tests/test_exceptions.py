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

import uuid

import pytest
import requests
from requests.utils import CaseInsensitiveDict
from requests_mock import Mocker

from ansys.openapi.common import ApiConnectionException, ApiException
from ansys.openapi.common._exceptions import AuthenticationWarning


def test_api_connection_exception_repr():
    args = {
        "url": "http://protected.url/path/to/resource",
        "status_code": 403,
        "reason": "Forbidden",
        "text": "You do not have permission to access this resource",
    }

    with Mocker() as m:
        m.get(**args)
        response = requests.get(args["url"])

    assert response.status_code == args["status_code"]
    api_connection_exception = ApiConnectionException(response)
    assert all([str(v) in str(api_connection_exception) for v in args.values()])

    assert repr(response) in repr(api_connection_exception)


def test_api_exception_repr():
    status_code = 404
    reason_phrase = "Not Found"
    message = f'Record with ID "{str(uuid.uuid4())}" not found'

    api_exception = ApiException(status_code, reason_phrase, message)
    exception_repr = api_exception.__repr__()

    exception_from_repr = eval(exception_repr)
    assert isinstance(exception_from_repr, ApiException)
    assert exception_from_repr.status_code == api_exception.status_code
    assert exception_from_repr.reason_phrase == api_exception.reason_phrase
    assert exception_from_repr.body == api_exception.body


def test_authentication_warning():
    message = "OpenID Connect was requested but no authentication was required."

    authentication_warning = AuthenticationWarning(message)
    warning_repr = authentication_warning.__repr__()

    warning_from_repr = eval(warning_repr)
    assert isinstance(warning_from_repr, AuthenticationWarning)
    assert warning_from_repr.message == authentication_warning.message


@pytest.mark.parametrize("include_headers", (False, True))
@pytest.mark.parametrize("include_body", (False, True))
def test_api_exception_str(include_headers, include_body):
    status_code = 404
    reason_phrase = "Not Found"
    if include_headers:
        headers = CaseInsensitiveDict({"Content-Type": "application/json"})
    else:
        headers = None
    if include_body:
        body = f"Record with ID '{str(uuid.uuid4())}' not found"
    else:
        body = None
    api_connection_exception = ApiException(status_code, reason_phrase, body=body, headers=headers)
    exception_str = api_connection_exception.__str__()

    assert "ApiException" in exception_str
    assert str(status_code) in exception_str
    assert reason_phrase in exception_str
    if include_body:
        assert body in exception_str
    if include_headers:
        assert str(headers) in exception_str
