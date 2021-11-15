import http.cookiejar
import logging
import re
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import chain
from typing import Dict, Union, Tuple
from ._exceptions import ApiException

try:
    from typing import TypedDict
except ImportError:
    from typing_extensions import TypedDict, Type

import tempfile

import requests
from requests.structures import CaseInsensitiveDict

"""
LICENSE: parse_authenticate, _group_challenges, _group_pairs
  
Copyright (c) 2015 Alexander Dutton.
All rights reserved.

Redistribution and use in source and binary forms are permitted
provided that the above copyright notice and this paragraph are
duplicated in all such forms and that any documentation,
advertising materials, and other materials related to such
distribution and use acknowledge that the software was developed
by the Alexander Dutton. The name of the Alexander Dutton may not
be used to endorse or promote products derived from this software
without specific prior written permission.
THIS SOFTWARE IS PROVIDED ``AS IS'' AND WITHOUT ANY EXPRESS OR
IMPLIED WARRANTIES, INCLUDING, WITHOUT LIMITATION, THE IMPLIED
WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
"""

_tokens = (
    ("token", re.compile(r"""^([!#$%&'*+\-.^_`|~\w/]+(?:={1,2}$)?)""")),
    ("token", re.compile(r'''^"((?:[^"\\]|\\\\|\\")+)"''')),
    (None, re.compile(r"^\s+")),
    ("equals", re.compile(r"^(=)")),
    ("comma", re.compile(r"^(,)")),
)


class CaseInsensitiveOrderedDict(OrderedDict):
    """[TECHDOCS]Dictionary object that preserves order of insertion and is case-insensitive. Intended for use when
    parsing www-authenticate headers where odd combinations of entries are expected.
    """

    __slots__ = ()

    @staticmethod
    def _process_args(mapping=(), **kwargs):
        if hasattr(mapping, "items"):
            mapping = getattr(mapping, "items")()
        return ((k.lower(), v) for k, v in chain(mapping, getattr(kwargs, "items")()))

    def __init__(self, mapping=(), **kwargs):
        super().__init__(self._process_args(mapping, **kwargs))

    def __getitem__(self, k):
        return super().__getitem__(k.lower())

    def __setitem__(self, k, v):
        return super().__setitem__(k.lower(), v)

    def __delitem__(self, k):
        return super().__delitem__(k.lower())

    def get(self, k, default=None):
        return super().get(k.lower(), default)

    def setdefault(self, k, default=None):
        return super().setdefault(k.lower(), default)

    def pop(self, k, v=object()):
        if v is object():
            return super().pop(k.lower())
        return super().pop(k.lower(), v)

    def update(self, mapping=(), **kwargs):
        super().update(self._process_args(mapping, **kwargs))

    def __contains__(self, k):
        return super().__contains__(k.lower())

    def copy(self):
        return type(self)(self)

    @classmethod
    def fromkeys(cls, keys, v=None):
        return super().fromkeys((k.lower() for k in keys), v)

    def __repr__(self):
        return "{0}({1})".format(type(self).__name__, super().__repr__())


def _group_pairs(tokens):
    i = 0
    while i < len(tokens) - 2:
        if (
            tokens[i][0] == "token"
            and tokens[i + 1][0] == "equals"
            and tokens[i + 2][0] == "token"
        ):
            tokens[i : i + 3] = [("pair", (tokens[i][1], tokens[i + 2][1]))]
        i += 1


def _group_challenges(tokens):
    challenges = []
    while tokens:
        j = 1
        if len(tokens) == 1:
            pass
        elif tokens[1][0] == "comma":
            pass
        elif tokens[1][0] == "token":
            j = 2
        else:
            while j < len(tokens) and tokens[j][0] == "pair":
                j += 2
            j -= 1
        challenges.append((tokens[0][1], tokens[1:j]))
        tokens[: j + 1] = []
    return challenges


def parse_authenticate(value):
    """[TECHDOCS]Parses a string containing a `WWW-AUTHENTICATE` header and returns a dictionary with the supported
    authentication types and the provided parameters (if any exist)

    Parameters
    ----------
    value : str
        A WWW-AUTHENTICATE header

    Returns
    -------
    CaseInsensitiveOrderedDict
        Dictionary with supported auth types and the provided parameters (if any)
    """
    tokens = []
    while value:
        for token_name, pattern in _tokens:
            match = pattern.match(value)
            if match:
                value = value[match.end() :]
                if token_name:
                    tokens.append((token_name, match.group(1)))
                break
        else:
            raise ValueError("Failed to parse value")
    _group_pairs(tokens)

    challenges = CaseInsensitiveOrderedDict()
    for name, tokens in _group_challenges(tokens):
        args, kwargs = [], {}
        for token_name, value in tokens:
            if token_name == "token":
                args.append(value)
            elif token_name == "pair":
                kwargs[value[0]] = value[1]
        challenges[name] = (args and args[0]) or kwargs or None

    return challenges


def set_session_kwargs(
    session: requests.Session, property_dict: "RequestsConfiguration"
) -> None:
    """[TECHDOCS]Sets session parameters from a provided dictionary

    Parameters
    ----------
    session : :obj:`requests.Session`
        requests Session object to be configured
    property_dict : dict
        Mapping from requests session parameter to value

    Returns
    -------
    None
    """
    for k, v in property_dict.items():
        session.__dict__[k] = v


class ResponseHandler(BaseHTTPRequestHandler):
    """[TECHDOCS]OIDC Callback handler, returns authentication complete page when authentication flow completes.

    Attributes
    ----------
    _response_html : str
        HTML to be rendered to the user when redirected after successful authentication with the IDP
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._response_html = (
            r"<!DOCTYPE html>"
            r'    <html lang="en">'
            r"        <head>"
            r'            <meta charset="UTF-8">'
            r"        <title>{title}</title>"
            r"    </head>"
            r"    <body>"
            r"        <h1>{title}</h1>"
            r"        <p>{paragraph}</p>"
            r"    </body>"
            r"</html>".format(
                title="Login successful", paragraph="You can now close this tab."
            ).encode("utf-8")
        )

    # noinspection PyPep8Naming
    def do_GET(self) -> None:
        """[TECHDOCS]Handle GET requests to the callback URL"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        self.wfile.write(self._response_html)
        # noinspection PyProtectedMember
        self.server._auth_code.put("https://localhost{}".format(self.path))  # type: ignore[attr-defined]


class OIDCCallbackHTTPServer(HTTPServer):
    """[TECHDOCS]HTTP Server to handle callback requests on successful OpenID Connect authentication.

    Attributes
    ----------
    _auth_code : Queue
        Store for provided authentication code received from the user's browser when authentication completes
    """

    def __init__(self):
        from queue import Queue

        super().__init__(("", 32284), ResponseHandler)
        self._auth_code = Queue()

    async def get_auth_code(self):
        return self._auth_code.get(block=True)


class SessionConfiguration:
    """Provides configuration for the API client session"""

    def __init__(
        self,
        client_cert_path: str = None,
        client_cert_key: str = None,
        cookies: http.cookiejar.CookieJar = None,
        headers: CaseInsensitiveDict = None,
        max_redirects: int = 10,
        proxies: Dict[str, str] = None,
        verify_ssl: bool = True,
        cert_store_path: str = None,
        temp_folder_path: str = None,
        debug: bool = False,
        safe_chars_for_path_param: str = "",
        retry_count: int = 3,
        request_timeout: int = 31,
    ):
        """
        Parameters
        ----------
        client_cert_path : str
            Path to client certificate to be sent with requests, see requests.Session.cert.
        client_cert_key : str
            Key to unlock client certificate, see requests.Session.cert.
        cookies : http.cookiejar.CookieJar or subclass
            Cookies to be sent with each request.
        headers : dict
            Header values to include with each request indexed by header name, case-insensitive.
        max_redirects : int
            Maximum number of requests to allow before halting.
        proxies : dict
            Proxy server urls indexed by resource urls.
        verify_ssl : bool
            Verify the SSL certificate of the remote host (default True).
        cert_store_path : str
            Path to custom certificate store (in .pem format)
        temp_folder_path : str
            Path to temporary directory where downloaded files will be stored (default is user TEMP directory)
        debug : bool
            Controls whether debug logging will be generated, this will include sensitive information if either the
            `auth_logger` or `transport_logger` are configured to output logs.
        safe_chars_for_path_param : str
            Additional characters to treat as 'safe' when creating path parameters, see
            `RFC 3986 <https://datatracker.ietf.org/doc/html/rfc3986#section-2.2>`_ for more information
        retry_count : int
            Number of attempts to make if the API server fails to return a valid response (default 3).
        request_timeout : int
            Timeout for requests to the API server in seconds (default 31).
        """
        self.client_cert_path = client_cert_path
        self.client_cert_key = client_cert_key
        self.cookies = cookies or http.cookiejar.CookieJar()
        self.headers = headers or CaseInsensitiveDict()
        self.max_redirects = max_redirects
        self.proxies = proxies or {}
        self.verify_ssl = verify_ssl
        self.cert_store_path = cert_store_path
        self.temp_folder_path = temp_folder_path or tempfile.gettempdir()
        self.debug = debug
        self.safe_chars_for_path_param = safe_chars_for_path_param
        self.retry_count = retry_count
        self.request_timeout = request_timeout

    @property
    def _cert(self) -> Union[None, str, Tuple[str, str]]:
        if self.client_cert_path is None:
            return None
        elif self.client_cert_key is None:
            return self.client_cert_path
        else:
            return self.client_cert_path, self.client_cert_key

    @property
    def _verify(self) -> Union[None, bool, str]:
        if self.verify_ssl is None:
            return None
        elif self.cert_store_path is None:
            return self.verify_ssl
        else:
            return self.cert_store_path

    def get_configuration_for_requests(
        self,
    ) -> "RequestsConfiguration":
        """
        Output configuration as a dictionary with keys corresponding to requests session properties.

        Returns
        -------
        RequestsConfiguration
            The configuration as a dictionary suitable for configuring a requests Session
        """
        output: RequestsConfiguration = {
            "cert": self._cert,
            "verify": self._verify,
            "cookies": self.cookies,
            "proxies": self.proxies,
            "headers": self.headers,
            "max_redirects": self.max_redirects,
        }
        return output

    @classmethod
    def from_dict(
        cls, configuration_dict: "RequestsConfiguration"
    ) -> "SessionConfiguration":
        """
        Create a SessionConfiguration object from its dictionary form, inverse of
        :meth:`.get_configuration_for_requests`.
        :param configuration_dict: dict form of the session parameters
        :return: session configuration object
        """
        new = cls()
        if configuration_dict["cert"] is not None:
            cert = configuration_dict["cert"]
            if isinstance(cert, tuple):
                new.client_cert_path = cert[0]
                new.client_cert_key = cert[1]
            elif isinstance(cert, str):
                new.client_cert_path = cert
            else:
                raise ValueError(
                    f"[TECHDOCS]Invalid 'cert' field, must be Tuple or str, not '{type(cert)}'"
                )
        if configuration_dict["verify"] is not None:
            verify = configuration_dict["verify"]
            if isinstance(verify, str):
                new.verify_ssl = True
                new.cert_store_path = verify
            elif isinstance(verify, bool):
                new.verify_ssl = verify
            else:
                raise ValueError(
                    f"[TECHDOCS]Invalid 'verify' field, must be str or bool, not '{type(verify)}'"
                )
        new.cookies = configuration_dict["cookies"]
        new.proxies = configuration_dict["proxies"]
        new.headers = configuration_dict["headers"]
        new.max_redirects = configuration_dict["max_redirects"]
        return new


class RequestsConfiguration(TypedDict):
    cert: Union[None, str, Tuple[str, str]]
    verify: Union[None, str, bool]
    cookies: http.cookiejar.CookieJar
    proxies: Dict[str, str]
    headers: CaseInsensitiveDict
    max_redirects: int


class ModelType(type):
    """Metaclass for all models. Enables easier type hinting
    in packages that interact with generated code."""

    attribute_map: dict
    swagger_types: dict


def handle_response(response: requests.Response) -> requests.Response:
    """Helper method to check the status code of a response

    If the response is a 2XX then it is returned as-is, otherwise an ApiException will be raised

    Parameters
    ----------
    response : requests.Response
        Response from the API server

    Returns
    -------
    requests.Response
        The response as-is if the status_code was 2XX

    Throws
    ------
    ApiException
        If the status code was not 2XX
    """
    logger = logging.getLogger(__name__)

    logger.debug(f"response body: {response.text}")
    if not 200 <= response.status_code <= 299:
        raise ApiException.from_response(response)
    return response
