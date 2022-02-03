from typing import Optional

from requests.structures import CaseInsensitiveDict

MYPY = False
if MYPY:
    import requests


class ApiConnectionException(Exception):
    """
    Provides the exception to raise when connection to the API server fails. For more information
    about the failure, inspect ``.status_code`` and ``.reason_phrase``.

    Attributes
    ----------
    status_code : int
        HTTP status code associated with the response.
    reason_phrase : str
        Description of the response provided by the server.
    message : str
        Content of the response provided by the server.

    """

    def __init__(self, status_code: int, reason_phrase: str, message: str):
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.message = message
        super().__init__(message)

    def __repr__(self) -> str:
        return f"ApiConnectionException({self.status_code}, '{self.reason_phrase}','{self.message}')"


class AuthenticationWarning(Warning):
    """
    Provides the warning to raise when the server connection process completes but does proceed as expected.
    """

    def __init__(self, message: str) -> None:
        """
        Parameters
        ----------
        message : str
            Cause of the warning and any additional information.
        """
        self.message = message

    def __repr__(self) -> str:
        return f"AuthenticationWarning('{self.message}')"


class ApiException(Exception):
    """
    Provides the exception to raise when the remote server returns an unsuccessful response. For more information
    about the failure, inspect ``.status_code`` and ``.reason_phrase``.

    Attributes
    ----------
    status_code : int
        HTTP status code associated with the response.
    reason_phrase : str
        Description of the response provided by the server.
    body : str, optional
        Content of the response provided by the server. The default is ``None``.
    headers : CaseInsensitiveDict, optional
        Response headers provided by the server. The defeault is ``None``.
    """

    status_code: int
    reason_phrase: str
    body: Optional[str]
    headers: Optional[CaseInsensitiveDict]

    def __init__(
        self,
        status_code: int,
        reason_phrase: str,
        body: Optional[str] = None,
        headers: Optional[CaseInsensitiveDict] = None,
    ):
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.body = body
        self.headers = headers

    @classmethod
    def from_response(cls, http_response: "requests.Response") -> "ApiException":
        new = cls(
            status_code=http_response.status_code,
            reason_phrase=http_response.reason,
            body=http_response.text,
            headers=http_response.headers,
        )
        return new

    def __str__(self) -> str:
        error_message = f"ApiException({self.status_code}, '{self.reason_phrase}')\n"
        if self.headers:
            error_message += f"HTTP response headers: {self.headers}\n"
        if self.body:
            error_message += f"HTTP response body: {self.body}\n"
        return error_message

    def __repr__(self) -> str:
        return (
            f"ApiException({self.status_code}, '{self.reason_phrase}', '{self.body}')"
        )
