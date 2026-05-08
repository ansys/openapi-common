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
import typing
from collections import OrderedDict
import http.cookiejar
from itertools import chain
import tempfile
import urllib.parse
from typing import (
    Any,
    Collection,
    Dict,
    List,
    Optional,
    Tuple,
    TypedDict,
    Union,
    cast,
)

import httpx
import pyparsing as pp
from ._case_insensitive_dict import CaseInsensitiveDict

from ._retry_transport import RetryingHTTPTransport


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
        """Override __getitem__ to retrieve lower-case key."""
        return super().__getitem__(k.lower())

    def __setitem__(self, k: str, v: Any) -> None:
        """Override __setitem__ to store lower-case key."""
        return super().__setitem__(k.lower(), v)

    def __delitem__(self, k: str) -> None:
        """Override __delitem__ to delete lower-case key."""
        return super().__delitem__(k.lower())

    def get(self, k: str, default: Optional[Any] = None) -> Any:
        """Override get to retrieve lower-case key."""
        return super().get(k.lower(), default)

    def setdefault(self, k: str, default: Optional[Any] = None) -> Any:
        """Override setdefault to use lower-case key."""
        return super().setdefault(k.lower(), default)

    def pop(self, k: str, v: Any = object()) -> Any:
        """Override pop to use lower-case key."""
        if v is object():
            return super().pop(k.lower())
        return super().pop(k.lower(), v)

    def update(self, mapping: Any = (), **kwargs: Any) -> None:  # type: ignore[override]
        """Override update to use lower-case key."""
        super().update(self._process_args(mapping, **kwargs))

    def __contains__(self, k: str) -> bool:  # type: ignore[override]
        """Override __contains__ to use lower-case key."""
        return super().__contains__(k.lower())

    def copy(self) -> "CaseInsensitiveOrderedDict":
        """Override copy."""
        return type(self)(self)

    @classmethod
    @typing.no_type_check
    def fromkeys(
        cls,
        keys: Collection[str],
        v: Optional[Any] = None,
    ) -> "CaseInsensitiveOrderedDict":
        """Override fromkeys to use lower-case keys."""
        return cast("CaseInsensitiveOrderedDict", super().fromkeys((k.lower() for k in keys), v))

    def __repr__(self) -> str:
        """Printable representation of the object."""
        return "{0}({1})".format(type(self).__name__, super().__repr__())


class Singleton(type):
    """
    Metaclass that adds Singleton behaviour.

    When derived classes are created for the first time, they are added to the ``._instances`` property. Further instances of the
    class will fetch the existing instance, rather than creating a new one.
    """

    _instances: Dict[type, object] = {}

    def __call__(cls, *args: Any, **kwargs: Any) -> Any:
        """Invoke when calling this object."""
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
        token68 = pp.Combine(pp.Word(token68_char) + pp.ZeroOrMore(pp.Word("=")))

        name = pp.Word(pp.alphas, pp.alphanums)
        value = pp.quoted_string.set_parse_action(pp.remove_quotes)
        name_value_pair = name + pp.Suppress("=") + value

        params = pp.Dict(pp.DelimitedList(pp.Group(name_value_pair)))

        credentials = token + (params ^ token68) ^ token

        self.auth_parser = pp.DelimitedList(credentials("schemes*"), delim=", ")

    def parse_header(self, value: str) -> CaseInsensitiveOrderedDict:
        """Parse a given header's content and return a dictionary of authentication methods and parameters or tokens.

        Invalid headers (according to the specification above) will return an empty response.

        Parameters
        ----------
        value : str
            Contents of a ``WWW-Authenticate`` header.
        """
        try:
            parsed_value = self.auth_parser.parse_string(value, parse_all=True)
        except pp.ParseException as exception_info:
            raise ValueError("Failed to parse value").with_traceback(exception_info.__traceback__)
        output = CaseInsensitiveOrderedDict({})
        for scheme in parsed_value.schemes:
            output[scheme[0]] = AuthenticateHeaderParser._render_options(scheme)
        return output

    @staticmethod
    def _render_options(
        scheme: List[Union[str, List[str]]],
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
    """Parse a string containing a ``WWW-Authenticate`` header.

    Return a dictionary with the supported authentication types and provided parameters
    (if any exist).

    Parameters
    ----------
    value : str
        A ``WWW-Authenticate`` header.
    """
    parser = AuthenticateHeaderParser()
    return parser.parse_header(value)


def _scheme_mount_prefix(url: str) -> str:
    scheme = urllib.parse.urlparse(url).scheme.lower()
    if scheme not in ("http", "https"):
        raise ValueError(
            f"mount_scheme_url must use http or https scheme (got {scheme!r} from {url!r})."
        )
    return f"{scheme}://"


def collect_www_authenticate_raw_values(response: httpx.Response) -> list[str]:
    """Return each raw ``WWW-Authenticate`` challenge line from ``response``.

    Multiple header field lines are preserved as separate entries (RFC 9110). ``httpx``
    exposes these via :meth:`httpx.Headers.get_list`.
    """
    return [v.strip() for v in response.headers.get_list("www-authenticate") if v.strip()]


class TransportConfiguration(TypedDict):
    """Serializable HTTP transport settings used to build :class:`httpx.Client`.

    These keys feed :func:`httpx_client_init_kwargs` for ``httpx.Client`` construction.
    """

    cert: Union[None, str, Tuple[str, str]]
    verify: Union[None, str, bool]
    cookies: http.cookiejar.CookieJar
    proxy_url: Optional[str]
    headers: CaseInsensitiveDict
    max_redirects: int


def httpx_client_init_kwargs(configuration: TransportConfiguration) -> dict[str, Any]:
    """Build keyword arguments for :class:`httpx.Client` from transport configuration.

    ``proxy_url`` is not applied here; it is handled in
    :func:`create_httpx_client_from_session_configuration` using a single ``httpx`` mount
    derived from ``mount_scheme_url``.

    Parameters
    ----------
    configuration : TransportConfiguration
        Output of :meth:`SessionConfiguration.get_transport_configuration`.

    Returns
    -------
    dict[str, Any]
        Keyword arguments suitable for ``httpx.Client(**kwargs)``.
    """
    headers = configuration["headers"]
    kwargs: dict[str, Any] = {
        "cert": configuration["cert"],
        "verify": configuration["verify"],
        "cookies": configuration["cookies"],
        "headers": dict(headers) if headers else {},
        "max_redirects": configuration["max_redirects"],
        # requests follows redirects by default; match that for future Client wiring.
        "follow_redirects": True,
    }
    return kwargs


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
    proxy_url : str, optional
        Outbound HTTP(S) proxy URL (e.g. ``http://proxy.corp:8080``). When set, pass
        ``mount_scheme_url`` to :func:`create_httpx_client_from_session_configuration`
        (for example the API base URL) so the correct ``http(s)://`` transport mount is used.
        The default is ``None`` (no proxy).
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
        proxy_url: Optional[str] = None,
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
        self.proxy_url = (proxy_url.strip() if proxy_url else None) or None
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

    def get_transport_configuration(
        self,
    ) -> TransportConfiguration:
        """Retrieve settings as a mapping aligned with HTTP client transport configuration."""
        output: TransportConfiguration = {
            "cert": self._cert,
            "verify": self._verify,
            "cookies": self.cookies,
            "proxy_url": self.proxy_url,
            "headers": self.headers,
            "max_redirects": self.max_redirects,
        }
        return output

    @classmethod
    def from_dict(cls, configuration_dict: TransportConfiguration) -> "SessionConfiguration":
        """
        Create a :class:`SessionConfiguration` object from its dictionary form.

        This is the inverse of the :meth:`.get_transport_configuration` method.

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
                raise ValueError(f"Invalid 'cert' field. Must be Tuple or str, not '{type(cert)}'.")
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
        if configuration_dict["proxy_url"] is not None:
            pu = configuration_dict["proxy_url"]
            if not isinstance(pu, str):
                raise ValueError(f"Invalid 'proxy_url' field. Must be str, not '{type(pu)}'.")
            new.proxy_url = pu.strip() or None
        if configuration_dict["headers"] is not None:
            new.headers = configuration_dict["headers"]
        if configuration_dict["max_redirects"] is not None:
            new.max_redirects = configuration_dict["max_redirects"]
        return new


def create_httpx_client_from_session_configuration(
    session_configuration: SessionConfiguration,
    *,
    mount_scheme_url: Optional[str] = None,
) -> httpx.Client:
    """Create a synchronous :class:`httpx.Client` from a :class:`SessionConfiguration`.

    Uses :class:`~ansys.openapi.common._retry_transport.RetryingHTTPTransport` so connection
    failures, timeouts, and selected HTTP status codes are retried according to
    ``session_configuration.retry_count`` (maximum total attempts per request).

    When ``SessionConfiguration.proxy_url`` is set, ``mount_scheme_url`` (for example the
    API base URL) is **required**. Its scheme selects a single ``httpx`` mount
    (``http://`` or ``https://``) that uses the proxy; the default transport handles other
    schemes without a proxy (for example redirects).

    Parameters
    ----------
    session_configuration : SessionConfiguration
        Source configuration for TLS, cookies, headers, redirects, timeout, proxy, and retries.
    mount_scheme_url :
        URL whose scheme determines the proxy mount when ``proxy_url`` is set. Ignored when
        ``proxy_url`` is unset.

    Returns
    -------
    httpx.Client
        Configured HTTP client.
    """
    kwargs = httpx_client_init_kwargs(session_configuration.get_transport_configuration())
    kwargs["timeout"] = session_configuration.request_timeout

    verify = kwargs.pop("verify", True)
    cert = kwargs.pop("cert", None)

    proxy_url = session_configuration.proxy_url
    attempts = max(1, session_configuration.retry_count)
    backoff = 0.3

    default_transport = RetryingHTTPTransport(
        verify=verify,
        cert=cert,
        proxy=None,
        max_attempts=attempts,
        backoff_factor=backoff,
    )
    kwargs["transport"] = default_transport

    if proxy_url is not None:
        if mount_scheme_url is None:
            raise ValueError(
                "mount_scheme_url is required when SessionConfiguration.proxy_url is set "
                "(for example the API base URL)."
            )
        mount_prefix = _scheme_mount_prefix(mount_scheme_url)
        proxied_transport = RetryingHTTPTransport(
            verify=verify,
            cert=cert,
            proxy=proxy_url,
            max_attempts=attempts,
            backoff_factor=backoff,
        )
        kwargs["mounts"] = {mount_prefix: proxied_transport}

    return httpx.Client(**kwargs)


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
    return (
        f"{package_name}/{package_version} {python_implementation}/{python_version} ({os_version})"
    )
