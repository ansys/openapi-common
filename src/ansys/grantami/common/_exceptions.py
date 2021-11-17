from typing import Optional

from requests.structures import CaseInsensitiveDict

MYPY = False
if MYPY:
    import requests


class ApiConnectionException(Exception):
    """
    Exception raised when connection to MI Servicelayer fails. Inspect the `.status_code` and `.reason_phrase` for more
    information about the failure.
    """

    def __init__(self, status_code: int, reason_phrase: str, message: str) -> None:
        """
        Parameters
        ----------
        status_code : int
            HTTP status code associated with the response.
        reason_phrase : str
            Description of the response as provided by the server.
        message : str
            The content of the response as provided by the server.
        """
        self.status_code = status_code
        self.reason_phrase = reason_phrase
        self.message = message
        super().__init__(message)

    def __repr__(self) -> str:
        return f"[TECHDOCS]ApiConnectionException({self.status_code}, '{self.reason_phrase}',\n'{self.message}')"


class ApiException(Exception):
    """
    Exception raised when the remote server returns an unsuccessful response. Inspect the `.status` and `.reason` for
    more information about the failure.

    Attributes
    ----------
    status_code : int
        HTTP status code associated with the response.
    reason_phrase : str
        Description of the response as provided by the server.
    body : Optional[str]
        Content of the response as provided by the server.
    headers : Optional[CaseInsensitiveDict]
        Response headers as provided by the server.
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
        """
        Parameters
        ----------
        status_code : int
            HTTP status code associated with the response.
        reason_phrase : str
            Description of the response as provided by the server.
        body : Optional[str]
            Contents of the response message, if present.
        headers : Optional[CaseInsensitiveDict]
            Headers dictionary, if present.

        Examples
        --------
        >>>raise ApiConnectionException(status_code=404, reason_phrase='Not Found')
        Traceback (most recent call last):
          File "<input>", line 1, in <module>
        ApiException(404, 'Not Found')
        """
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
        error_message = (
            f"[TECHDOCS]ApiException({self.status_code}, '{self.reason_phrase}')\n"
        )
        if self.headers:
            error_message += f"HTTP response headers: {self.headers}\n"
        if self.body:
            error_message += f"HTTP response body: {self.body}\n"
        return error_message

    def __repr__(self) -> str:
        return f"[TECHDOCS]ApiException({self.status_code}, {self.reason_phrase}, {self.body})"
