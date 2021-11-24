import uuid

import pytest
from requests.utils import CaseInsensitiveDict

from ansys.grantami.common import ApiException, ApiConnectionException
from ansys.grantami.common._exceptions import AuthenticationWarning


@pytest.mark.skip("Awaiting documentation review")
def test_api_connection_exception_repr():
    status_code = 403
    reason_phrase = "Forbidden"
    message = "You do not have permission to access this resource"

    api_connection_exception = ApiConnectionException(status_code, reason_phrase, message)
    exception_repr = api_connection_exception.__repr__()

    exception_from_repr = eval(exception_repr)
    assert exception_from_repr == api_connection_exception


@pytest.mark.skip("Awaiting documentation review")
def test_api_exception_repr():
    status_code = 404
    reason_phrase = "Not Found"
    message = f"Record with ID '{str(uuid.uuid4())}' not found"

    api_connection_exception = ApiException(status_code, reason_phrase, message)
    exception_repr = api_connection_exception.__repr__()

    exception_from_repr = eval(exception_repr)
    assert exception_from_repr == api_connection_exception


@pytest.mark.skip("Awaiting documentation review")
def test_authentication_warning():
    message = f"OpenID Connect was requested but no authentication was required."

    authentication_warning = AuthenticationWarning(message)
    warning_repr = authentication_warning.__repr__()

    warning_from_repr = eval(warning_repr)
    assert warning_from_repr == authentication_warning


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
