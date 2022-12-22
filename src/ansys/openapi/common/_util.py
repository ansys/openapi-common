import http.cookiejar
import sys

import pyparsing as pp
from collections import OrderedDict
from http.server import BaseHTTPRequestHandler, HTTPServer
from itertools import chain
from typing import Dict, Union, List, Optional, Tuple, Any, Collection, cast

from pyparsing import Word

from ._exceptions import ApiException
from ._logger import logger

if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict, Type

import tempfile

import requests
from requests.structures import CaseInsensitiveDict


class CaseInsensitiveOrderedDict(OrderedDict):
    """Preserves order of insertion and is case-insensitive.

    This class is intended for use when parsing ``WWW-Authenticate`` headers where odd combinations of entries
    are expected.
    """

    __slots__ = ()

    @staticmethod
    def _process_args(mapping: Any = (), **kwargs: Any) -> Any:
        if hasattr(mapping, "items"):
            mapping = getattr(mapping, "items")()
        return ((k.lower(), v) for k, v in chain(mapping, getattr(kwargs, "items")()))

    def __init__(self, mapping: Any = (), **kwargs: Any) -> None:
        super().__init__(self._process_args(mapping, **kwargs))

    def __getitem__(self, k: str) -> Any:
        return super().__getitem__(k.lower())

    def __setitem__(self, k: str, v: Any) -> None:
        return super().__setitem__(k.lower(), v)

    def __delitem__(self, k: str) -> None:
        return super().__delitem__(k.lower())

    def get(self, k: str, default: Optional[Any] = None) -> Any:
        return super().get(k.lower(), default)

    def setdefault(self, k: str, default: Optional[Any] = None) -> Any:
        return super().setdefault(k.lower(), default)

    def pop(self, k: str, v: Any = object()) -> Any:
        if v is object():
            return super().pop(k.lower())
        return super().pop(k.lower(), v)

    def update(self, mapping: Any = (), **kwargs: Any) -> None:  # type: ignore[override]
        super().update(self._process_args(mapping, **kwargs))

    def __contains__(self, k: str) -> bool:  # type: ignore[override]
        return super().__contains__(k.lower())

    def copy(self) -> "CaseInsensitiveOrderedDict":
        return type(self)(self)

    @classmethod
    def fromkeys(cls, keys: Collection[str], v: Optional[Any] = None) -> "CaseInsensitiveOrderedDict":  # type: ignore[override]
        return cast(
            "CaseInsensitiveOrderedDict", super().fromkeys((k.lower() for k in keys), v)
        )

    def __repr__(self) -> str:
        return "{0}({1})".format(type(self).__name__, super().__repr__())


class Singleton(type):
    """
    Metaclass that adds Singleton behaviour.

    When derived classes are created for the first time, they are added to the ``._instances`` property. Further instances of the
    class will fetch the existing instance, rather than creating a new one.
    """

    _instances: Dict[type, object] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class AuthenticateHeaderParser(metaclass=Singleton):
    """Parses ``WWW-Authenticate`` headers.

    This parser implements the RFC-7235 specification for the ``WWW-Authenticate`` header, together with
    the extension by Microsoft to support Negotiate authentication. This is a Singleton, because there is
    a non-trivial amount of work to set the parser engine up.
    """

    def __init__(self) -> None:
        token_char = "!#$%&'*+-.^_`|~" + pp.nums + pp.alphas
        token68_char = "-._~+/" + pp.nums + pp.alphas

        token = pp.Word(token_char)
        token68 = pp.Combine(pp.Word(token68_char) + pp.ZeroOrMore(Word("=")))

        name = pp.Word(pp.alphas, pp.alphanums)
        value = pp.quotedString.setParseAction(pp.removeQuotes)
        name_value_pair = name + pp.Suppress("=") + value

        params = pp.Dict(pp.delimitedList(pp.Group(name_value_pair)))

        credentials = token + (params ^ token68) ^ token

        self.auth_parser = pp.delimitedList(credentials("schemes*"), delim=", ")

    def parse_header(self, value: str) -> CaseInsensitiveOrderedDict:
        """Parse a given header's content and return a dictionary of authentication methods and parameters or tokens.

        Invalid headers (according to the specification above) will return an empty response.

        Parameters
        ----------
        value : str
            Contents of a ``WWW-Authenticate`` header.
        """
        try:
            parsed_value = self.auth_parser.parseString(value, parseAll=True)
        except pp.ParseException as exception_info:
            raise ValueError("Failed to parse value").with_traceback(
                exception_info.__traceback__
            )
        output = CaseInsensitiveOrderedDict({})
        for scheme in parsed_value.schemes:
            output[scheme[0]] = AuthenticateHeaderParser._render_options(scheme)
        return output

    @staticmethod
    def _render_options(
        scheme: List[Union[str, List[str]]]
    ) -> Optional[Union[str, CaseInsensitiveOrderedDict]]:
        if len(scheme) == 1:
            return None
        if isinstance(scheme[1], str):
            return scheme[1]
        scheme_options = scheme[1:]
        return CaseInsensitiveOrderedDict(
            {option_pair[0]: option_pair[1] for option_pair in scheme_options}
        )


def parse_authenticate(value: str) -> CaseInsensitiveOrderedDict:
    """Parse a string containing a ``WWW-Authenticate`` header and return a dictionary with the supported
    authentication types and provided parameters (if any exist).

    Parameters
    ----------
    value : str
        A ``WWW-Authenticate`` header.
    """
    parser = AuthenticateHeaderParser()
    return parser.parse_header(value)


def set_session_kwargs(
    session: requests.Session, property_dict: "RequestsConfiguration"
) -> None:
    """Set session parameters from the dictionary provided.

    Parameters
    ----------
    session : :obj:`requests.Session`
        Session object to configure.
    property_dict : dict
        Mapping from requests session parameter to value.
    """
    for k, v in property_dict.items():
        session.__dict__[k] = v


class RequestsConfiguration(TypedDict):
    cert: Union[None, str, Tuple[str, str]]
    verify: Union[None, str, bool]
    cookies: http.cookiejar.CookieJar
    proxies: Dict[str, str]
    headers: CaseInsensitiveDict
    max_redirects: int


class SessionConfiguration:
    """Provides configuration for the API client session.

    Parameters
    ----------
    client_cert_path : str, optional
        Path to the client certificate to send with the requests. The default is ``None``, in which case
        no client certificate will be sent with requests.
    client_cert_key : str, optional
        Key to unlock the client certificate (if required). The default is ``None``.
    cookies : :class:`http.cookiejar.CookieJar` or subclass, optional
        Cookies to send with each request. The default is ``None``.
    headers : dict, optional
        Header values to include with each request, indexed by header name. This parameter is
        case-insensitive. The default is ``None``, in which case only required headers will be included.
    max_redirects : int, optional
        Maximum number of redirects to allow before halting. The default is ``10``.
    proxies : dict, optional
        Proxy server URLs, indexed by resource URLs. The default is ``None``, in which case
        no proxies are registered for use.
    verify_ssl : bool, optional
        Whether to verify the SSL certificate of the remote host. The default is ``True``.
    cert_store_path : str, optional
        Path to the custom certificate store in ``.pem`` format.  The default is ``None``, in which case
        only certificates included in the ``certifi`` package will be trusted.
    temp_folder_path : str, optional
        Path to the temporary directory where downloaded files are to be stored. The default is
        ``None``, in which case the user's ``TEMP`` directory will be used.
    debug : bool, optional
        Whether a debug log is generated. The default is ``False``. The log include sensitives information
        about the authentication process.
    safe_chars_for_path_param : str, optional
        Additional characters to treat as 'safe' when creating path parameters. For more
        information, see `RFC 3986 <https://datatracker.ietf.org/doc/html/rfc3986#section-2.2>`_.
    retry_count : int, optional
        Number of attempts to make if the API server fails to return a valid response. The default is ``3``.
    request_timeout : int, optional
        Timeout in seconds for requests to the API server. The default is ``31``.
    """

    def __init__(
        self,
        client_cert_path: Optional[str] = None,
        client_cert_key: Optional[str] = None,
        cookies: Optional[http.cookiejar.CookieJar] = None,
        headers: Optional[CaseInsensitiveDict] = None,
        max_redirects: int = 10,
        proxies: Optional[Dict[str, str]] = None,
        verify_ssl: bool = True,
        cert_store_path: Optional[str] = None,
        temp_folder_path: Optional[str] = None,
        debug: bool = False,
        safe_chars_for_path_param: str = "",
        retry_count: int = 3,
        request_timeout: int = 31,
    ) -> None:
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
        if self.cert_store_path is None:
            return self.verify_ssl
        else:
            return self.cert_store_path

    def get_configuration_for_requests(
        self,
    ) -> "RequestsConfiguration":
        """
        Retrieve the configuration as a dictionary, with keys corresponding to ``requests`` session properties.
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
        Create a :class:`SessionConfiguration` object from its dictionary form, which is the inverse of
        the :meth:`.get_configuration_for_requests` method.

        Parameters
        ----------
        configuration_dict : dict
            Dictionary form of the session parameters.
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
                    f"Invalid 'cert' field. Must be Tuple or str, not '{type(cert)}'."
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
                    f"Invalid 'verify' field. Must be str or bool, not '{type(verify)}'."
                )
        if configuration_dict["cookies"] is not None:
            new.cookies = configuration_dict["cookies"]
        if configuration_dict["proxies"] is not None:
            new.proxies = configuration_dict["proxies"]
        if configuration_dict["headers"] is not None:
            new.headers = configuration_dict["headers"]
        if configuration_dict["max_redirects"] is not None:
            new.max_redirects = configuration_dict["max_redirects"]
        return new


def handle_response(response: requests.Response) -> requests.Response:
    """Check the status code of a response.

    If the response is 2XX, it is returned as-is. Otherwise an :class:`ApiException` class will be raised.

    Throws
    ------
    ApiException
        If the status code was not 2XX.

    Parameters
    ----------
    response : requests.Response
        Response from the API server.
    """
    logger.debug(f"response body: {response.text}")
    if not 200 <= response.status_code <= 299:
        raise ApiException.from_response(response)
    return response


def generate_user_agent(package_name: str, package_version: str) -> str:
    """Generate a user-agent string in the form *<package info> <python info> <os info>*.

    Parameters
    ----------
    package_name : str
        Name of the package to include in the user-agent string.
    package_version : str
        Version of the package to include in the user-agent string.

    Returns
    -------
    str
        User-agent string.
    """

    import platform

    python_implementation = platform.python_implementation()
    python_version = platform.python_version()
    os_version = platform.platform()
    return f"{package_name}/{package_version} {python_implementation}/{python_version} ({os_version})"
