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

import datetime
from enum import Enum
import json
import mimetypes
import os
import re
import tempfile
from types import ModuleType, TracebackType
from typing import (
    IO,
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Mapping,
    NamedTuple,
    NoReturn,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)
from urllib.parse import quote
import warnings

from dateutil.parser import parse
import httpx

from ._base import ApiClientBase, DeserializedType, ModelBase, PrimitiveType, SerializedType, Unset
from ._exceptions import ApiException, UndefinedObjectWarning
from ._logger import logger
from ._util import SessionConfiguration


def _close_distinct_httpx_auth_clients(rest_client: httpx.Client) -> None:
    """Close extra :class:`~httpx.Client` instances held by auth handlers (e.g. OIDC IdP).

    ``httpx-auth`` OAuth flows attach a dedicated client for token endpoint traffic so TLS
    settings can differ from the API client. Closing only the API client would otherwise
    leave that pool open.
    """
    auth = getattr(rest_client, "auth", None)
    if auth is None:
        return
    modes = getattr(auth, "authentication_modes", None)
    modes_list = list(modes) if modes is not None else [auth]
    seen: set[int] = set()
    for mode in modes_list:
        token_client = getattr(mode, "client", None)
        if not isinstance(token_client, httpx.Client):
            continue
        if token_client is rest_client:
            continue
        tid = id(token_client)
        if tid in seen:
            continue
        seen.add(tid)
        token_client.close()


class _CallRequestParts(NamedTuple):
    method: str
    url: str
    query_params_str: str
    header_params: Dict[str, Any]
    post_params: Optional[List[Tuple[Any, Any]]]
    body: Optional[Any]
    request_timeout: Union[float, Tuple[float, float], None]


async def _aclose_distinct_httpx_auth_clients(rest_client: httpx.AsyncClient) -> None:
    """Close distinct clients held by auth handlers (sync or async), excluding ``rest_client``."""
    auth = getattr(rest_client, "auth", None)
    if auth is None:
        return
    modes = getattr(auth, "authentication_modes", None)
    modes_list = list(modes) if modes is not None else [auth]
    seen: set[int] = set()
    for mode in modes_list:
        token_client = getattr(mode, "client", None)
        if isinstance(token_client, httpx.AsyncClient):
            if token_client is rest_client:
                continue
            tid = id(token_client)
            if tid in seen:
                continue
            seen.add(tid)
            await token_client.aclose()
        elif isinstance(token_client, httpx.Client):
            if token_client is rest_client:
                continue
            tid = id(token_client)
            if tid in seen:
                continue
            seen.add(tid)
            token_client.close()


# noinspection DuplicatedCode
class ApiClient(ApiClientBase):
    """Provides a generic API client for OpenAPI client library builds.

    This client handles client-server communication and is invariant across
    implementations. Specifics of the methods and models for each application are
    generated from OpenAPI templates and are responsible for interfacing with the
    public API exposed by the client.

    Parameters
    ----------
    session : httpx.Client
        HTTP client the API client uses (typically from :class:`ApiClientFactory`).
    api_url : str
        Base URL for the API. All generated endpoint URLs are relative to this address.
    configuration : SessionConfiguration
        Configuration options for the API client.

    Notes
    -----
    Call :meth:`close` when finished, or use ``with ApiClient(...) as client:``, so the
    underlying HTTP client releases its connection pool.

    Examples
    --------
    >>> transport = httpx.MockTransport(lambda request: httpx.Response(200))
    >>> client = ApiClient(httpx.Client(transport=transport),
    ...                    'http://my-api.com/API/v1.svc',
    ...                    SessionConfiguration())
    ... <ApiClient url: http://my-api.com/API/v1.svc>

    For testing purposes, it is common to configure an API with a self-signed certificate. By default, the
    :class:`ApiClient` class will not trust self-signed SSL certificates. To allow this, pass a path to the
    root certificate to the :class:`SessionConfiguration` object. For more configuration examples, see
    :class:`SessionConfiguration`.

    >>> session_config = SessionConfiguration(cert_store_path='./self-signed-cert.pem')
    ... ssl_client = ApiClient(httpx.Client(transport=transport),
    ...                    'https://secure-api/API/v1.svc',
    ...                    session_config)
    ... ssl_client
    <ApiClient url: https://secure-api/API/v1.svc>
    """

    PRIMITIVE_TYPES = (float, bool, bytes, str, int)
    NATIVE_TYPES_MAPPING = {
        "int": int,
        "bytes": bytes,
        "float": float,
        "str": str,
        "bool": bool,
        "date": datetime.date,
        "datetime": datetime.datetime,
    }
    LIST_MATCH_REGEX = re.compile(r"list\[(.*)]")
    DICT_MATCH_REGEX = re.compile(r"dict\(([^,]*), (.*)\)")

    def __init__(
        self,
        session: httpx.Client,
        api_url: str,
        configuration: SessionConfiguration,
    ):
        self.models: Dict[str, Union[Type[ModelBase], Type[Enum]]] = {}
        self.api_url = api_url
        self.rest_client = session
        self.configuration = configuration
        self._closed = False

    def close(self) -> None:
        """Close the underlying HTTP session or client and release connections.

        When ``rest_client`` is an :class:`~httpx.Client` whose auth handler owns a separate
        client (OpenID Connect token traffic to the IdP), that client is closed as well.
        """
        if self._closed:
            return
        self._closed = True
        rc = self.rest_client
        _close_distinct_httpx_auth_clients(rc)
        rc.close()

    def __enter__(self) -> "ApiClient":
        """Enter a context manager; returns this client."""
        return self

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Exit the context manager and close the underlying HTTP client."""
        self.close()

    def __repr__(self) -> str:
        """Printable representation of the object."""
        return f"<ApiClient url: {self.api_url}>"

    def setup_client(self, models: ModuleType) -> None:
        """Set up the client for use and register models for serialization and deserialization.

        This step must be completed prior to using the :class:`ApiClient` class.

        Parameters
        ----------
        models : ModuleType
            Module containing models generated by the Swagger code generator tool.

        Examples
        --------
        >>> tc = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        >>> client = ApiClient(tc,
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... import ApiModels as model_module
        ... client.setup_client(model_module)
        """
        self.models = models.__dict__

    def _build_call_request_parts(
        self,
        resource_path: str,
        method: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        header_params: Union[Dict[str, Union[str, int]], None] = None,
        body: Optional[Any] = None,
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[
            Mapping[str, Union[str, bytes, IO, Iterable[Union[str, bytes, IO]]]]
        ] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
    ) -> _CallRequestParts:
        header_params = header_params or {}
        if header_params:
            header_params_sanitized = self.sanitize_for_serialization(header_params)
            header_params = dict(
                self.parameters_to_tuples(header_params_sanitized, collection_formats)
            )

        if path_params:
            resource_path = self.__handle_path_params(
                resource_path, path_params, collection_formats
            )

        query_params_str = ""
        if query_params:
            query_params_str = self.__handle_query_params(query_params, collection_formats)

        if post_params or files:
            post_param_tuples = self.prepare_post_parameters(post_params, files)
            sanitized_post_params = self.sanitize_for_serialization(post_param_tuples)
            post_params = self.parameters_to_tuples(sanitized_post_params, collection_formats)

        if body:
            body = self.sanitize_for_serialization(body)
            if isinstance(body, (list, dict)):
                body = json.dumps(body).encode("utf8")
                header_params.setdefault("Content-Type", "application/json")

        url = self.api_url + resource_path
        return _CallRequestParts(
            method=method,
            url=url,
            query_params_str=query_params_str,
            header_params=header_params,
            post_params=post_params,
            body=body,
            request_timeout=_request_timeout,
        )

    def _finish_call_api(
        self,
        response_data: httpx.Response,
        response_type: Optional[str],
        _return_http_data_only: Optional[bool],
        response_type_map: Optional[Mapping[int, Union[str, None]]],
    ) -> Union[DeserializedType, Tuple[DeserializedType, int, httpx.Headers], None]:
        self.last_response = response_data
        logger.debug(f"response body: {response_data.text}")

        _response_type = response_type
        if response_type_map is not None:
            _response_type = response_type_map.get(response_data.status_code, None)

        deserialized_response = self.deserialize(response_data, _response_type)
        if not 200 <= response_data.status_code <= 299:
            raise ApiException.from_response(response_data, deserialized_response)
        return_data = deserialized_response

        if _return_http_data_only:
            return return_data
        else:
            return return_data, response_data.status_code, response_data.headers

    def __call_api(
        self,
        resource_path: str,
        method: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        header_params: Union[Dict[str, Union[str, int]], None] = None,
        body: Optional[Any] = None,
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[
            Mapping[str, Union[str, bytes, IO, Iterable[Union[str, bytes, IO]]]]
        ] = None,
        response_type: Optional[str] = None,
        _return_http_data_only: Optional[bool] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
        response_type_map: Optional[Mapping[int, Union[str, None]]] = None,
    ) -> Union[DeserializedType, Tuple[DeserializedType, int, httpx.Headers], None]:
        parts = self._build_call_request_parts(
            resource_path,
            method,
            path_params,
            query_params,
            header_params,
            body,
            post_params,
            files,
            collection_formats,
            _request_timeout,
        )
        response_data = self.request(
            parts.method,
            parts.url,
            query_params=parts.query_params_str,
            headers=parts.header_params,
            post_params=parts.post_params,
            body=parts.body,
            _request_timeout=parts.request_timeout,
        )
        return self._finish_call_api(
            response_data, response_type, _return_http_data_only, response_type_map
        )

    def __handle_path_params(
        self,
        resource_path: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None],
        collection_formats: Optional[Dict[str, str]],
    ) -> str:
        path_params_sanitized = self.sanitize_for_serialization(path_params)
        path_params_tuples = self.parameters_to_tuples(path_params_sanitized, collection_formats)
        for k, v in path_params_tuples:
            # specified safe chars, encode everything
            resource_path = resource_path.replace(
                f"{{{k}}}",
                quote(str(v), safe=self.configuration.safe_chars_for_path_param),
            )
        return resource_path

    def __handle_query_params(
        self,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None],
        collection_formats: Optional[Dict[str, str]],
    ) -> str:
        query_params_sanitized = self.sanitize_for_serialization(query_params)
        query_params_tuples = self.parameters_to_tuples(query_params_sanitized, collection_formats)
        return "&".join([f"{k}={v}" for k, v in query_params_tuples])

    def sanitize_for_serialization(self, obj: Any) -> Any:
        """Build a JSON POST object.

        Based on the object type, this method returns the sanitized JSON representation to send to the server:

        * If obj is ``None``, return ``None``.
        * If obj is ``str``, ``int``, ``float`` or ``bool``, return directly.
        * If obj is :class:`datetime.datetime` or :class:`datetime.date`, convert to string in ``iso8601`` format.
        * If obj is ``list``, sanitize each element in the ``list``.
        * If obj is ``tuple``, sanitize each element in the ``tuple``.
        * If obj is ``dict``, return the ``dict``.
        * If obj is an OpenAPI model, return the ``properties`` ``dict``.

        Parameters
        ----------
        obj : :obj:`.DeserializedType`
            Data to sanitize and serialize.

        Examples
        --------
        >>> tc = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        >>> client = ApiClient(tc,
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... client.sanitize_for_serialization({'key': 'value'})
        {'key': 'value'}

        >>> tc = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        >>> client = ApiClient(tc,
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... client.sanitize_for_serialization(datetime.datetime(2015, 10, 21, 10, 5, 10))
        '2015-10-21T10:05:10'
        """
        if obj is None:
            return None
        elif isinstance(obj, self.PRIMITIVE_TYPES):
            return obj
        elif isinstance(obj, list):
            return [self.sanitize_for_serialization(sub_obj) for sub_obj in obj]
        elif isinstance(obj, tuple):
            return tuple(self.sanitize_for_serialization(sub_obj) for sub_obj in obj)
        elif isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value

        if isinstance(obj, dict):
            obj_dict = obj
        else:
            obj_dict = {
                obj.attribute_map[attr]: getattr(obj, attr)
                for attr in obj.swagger_types
                if getattr(obj, attr) is not Unset
            }

        return {key: self.sanitize_for_serialization(val) for key, val in obj_dict.items()}

    def deserialize(
        self, response: httpx.Response, response_type: Optional[str]
    ) -> DeserializedType:
        """Deserialize the response into an object.

        Based on the type of response, the appropriate object is created for use.

        For responses that are in JSON format, this method processes the response and returns it:

        * If ``response_type`` is ``file``, save the content to a temporary file and return the file name.
        * If ``response_type`` is :class:`datetime.datetime` or :class:`datetime.date`, parse the string and return the
          ``datetime`` object.
        * If ``response_type`` is ``list``, recursively deserialize the list contents.
        * If ``response_type`` is ``dict``, recursively deserialize the dictionary keys and values.
        * If ``response_type`` is the name of an OpenAPI model, return the model object.

        Parameters
        ----------
        response : httpx.Response
            Response object received from the API.
        response_type : str
            String name of the class represented.

        Examples
        --------
        >>> tc = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        >>> client = ApiClient(tc,
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... api_response = httpx.Response(200, content=b'{"key": "value"}')
        ... client.deserialize(api_response, 'Dict[str, str]]')
        {'key': 'value'}

        >>> tc = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        >>> client = ApiClient(tc,
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... api_response = httpx.Response(200, content=b"'2015-10-21T10:05:10'")
        ... client.deserialize(api_response, 'datetime.datetime')
        datetime.datetime(2015, 10, 21, 10, 5, 10)
        """
        if response_type is None:
            return None

        if response_type == "file":
            return self.__deserialize_file(response)

        if response_type == "str":
            data: SerializedType = response.text
        else:
            try:
                data = response.json()
            except ValueError:
                data = response.content

        return self.__deserialize(data, response_type)

    def __deserialize(self, data: SerializedType, klass_name: str) -> DeserializedType:
        """Deserialize ``dict``, ``list``, and ``str`` into an object.

        Parameters
        ----------
        data : Union[dict, list, str]
            Response data to deserialize.
        klass_name : str
            Type of object to deserialize the data to. The type can be a:

            * String class name
            * String type definition for list or dictionary
            * "object" literal, which returns the dictionary as-is
        """
        if data is None:
            return None

        if klass_name == "object":
            warnings.warn(
                "Attempting to deserialize an object with no defined type. Returning "
                "the raw data as a dictionary. Check your OpenAPI definition and ensure "
                "all types are fully defined.",
                UndefinedObjectWarning,
            )
            return data

        list_match = self.LIST_MATCH_REGEX.match(klass_name)
        if list_match is not None:
            if not isinstance(data, list):
                raise TypeError(
                    f"Expected list for deserializing to {klass_name}, got {type(data)}"
                )
            sub_kls = list_match.group(1)
            return [self.__deserialize(sub_data, sub_kls) for sub_data in data]

        dict_match = self.DICT_MATCH_REGEX.match(klass_name)
        if dict_match is not None:
            if not isinstance(data, dict):
                raise TypeError(
                    f"Expected dict for deserializing to {klass_name}, got {type(data)}"
                )
            sub_kls = dict_match.group(2)
            return {k: self.__deserialize(v, sub_kls) for k, v in data.items()}

        if klass_name in self.NATIVE_TYPES_MAPPING:
            klass = self.NATIVE_TYPES_MAPPING[klass_name]
            if klass in self.PRIMITIVE_TYPES:
                if not isinstance(data, (str, int, float, bool, bytes)):
                    raise TypeError(
                        f"Expected primitive type for deserializing to {klass_name}, got {type(data)}"
                    )
                return self.__deserialize_primitive(data, klass)
            elif klass == datetime.date:
                if not isinstance(data, str):
                    raise TypeError(
                        f"Expected string for deserializing to {klass_name}, got {type(data)}"
                    )
                return self.__deserialize_date(data)
            elif klass == datetime.datetime:
                if not isinstance(data, str):
                    raise TypeError(
                        f"Expected string for deserializing to {klass_name}, got {type(data)}"
                    )
                return self.__deserialize_datetime(data)

        klass = self.models[klass_name]
        if issubclass(klass, Enum):
            return klass(data)
        else:
            if not isinstance(data, (dict, str)):
                raise TypeError(
                    f"Expected dict or string for deserializing to {klass_name}, got {type(data)}"
                )
            return self.__deserialize_model(data, klass)

    def call_api(
        self,
        resource_path: str,
        method: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        header_params: Union[Dict[str, Union[str, int]], None] = None,
        body: Optional[DeserializedType] = None,
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[Mapping[str, Union[str, bytes, IO]]] = None,
        response_type: Optional[str] = None,
        _return_http_data_only: Optional[bool] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
        response_type_map: Optional[Mapping[int, Union[str, None]]] = None,
    ) -> Union[DeserializedType, Tuple[DeserializedType, int, httpx.Headers], None]:
        """Make the HTTP request and return the deserialized data.

        Parameters
        ----------
        resource_path : str
            Path to the method endpoint, relative to the base URL.
        method : str
            HTTP method verb to call.
        path_params : Union[Dict[str, Union[str, int]], List[Tuple]]
            Path parameters to pass in the URL.
        query_params : Union[Dict[str, Union[str, int]], List[Tuple]]
            Query parameters to pass in the URL.
        header_params : Union[Dict[str, Union[str, int]], List[Tuple]]
            Header parameters to place in the request header.
        body : :obj:`.DeserializedType`
            Request body.
        post_params : Optional[List[Tuple[str, Union[str, bytes, IO]]]]
            Request POST form parameters for ``application/x-www-form-urlencoded`` and ``multipart/form-data``.
        response_type : str, optional
            Expected response data type.
        files : Optional[Mapping[str, Union[str, bytes, IO]]]
            Dictionary of the file name and path for ``multipart/form-data``.
        _return_http_data_only : bool, optional
            Whether to return response data without head status code and headers. The default
            is ``False``.
        collection_formats : Dict[str, str]
            Collection format name for path, query, header, and post parameters. This parameter maps the
            parameter name to the collection type.
        _request_timeout : Union[float, Tuple[float, float], None]
            Timeout setting for the request. If only one number is provided, it is used as a total request timeout.
            It can also be a pair (tuple) of (connection, read) timeouts. This parameter overrides the session-level
            timeout setting.
        response_type_map : Dict[int, Union[str, None]]
            Dictionary of response status codes and response types for response deserialization. If provided, has
            precedence over response_type.
        """
        return self.__call_api(
            resource_path,
            method,
            path_params,
            query_params,
            header_params,
            body,
            post_params,
            files,
            response_type,
            _return_http_data_only,
            collection_formats,
            _request_timeout,
            response_type_map,
        )

    @staticmethod
    def _url_with_query_string(url: str, query_params: Optional[str]) -> str:
        if not query_params:
            return url
        return f"{url}&{query_params}" if "?" in url else f"{url}?{query_params}"

    @staticmethod
    def _prepare_httpx_request_args(
        url: str,
        query_params: Optional[str],
        headers: Optional[Dict],
        post_params: Optional[
            Iterable[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]]
        ],
        body: Optional[Any],
        _request_timeout: Union[float, Tuple[float, float], None],
    ) -> Tuple[str, Dict[str, Any], Dict[str, Any]]:
        url_effective = ApiClient._url_with_query_string(url, query_params)
        kw: Dict[str, Any] = {
            "headers": headers,
            "timeout": _request_timeout,
        }
        body_kw: Dict[str, Any] = {}
        if post_params is not None:
            body_kw["files"] = post_params
        if body is not None:
            if post_params is not None:
                if isinstance(body, str):
                    body_kw["content"] = body.encode("utf-8")
                elif isinstance(body, bytes):
                    body_kw["content"] = body
                else:
                    body_kw["data"] = body
            elif isinstance(body, bytes):
                body_kw["content"] = body
            elif isinstance(body, str):
                body_kw["content"] = body.encode("utf-8")
            else:
                body_kw["data"] = body
        return url_effective, kw, body_kw

    def request(
        self,
        method: str,
        url: str,
        query_params: Optional[str] = None,
        headers: Optional[Dict] = None,
        post_params: Optional[
            Iterable[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]]
        ] = None,
        body: Optional[Any] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
    ) -> httpx.Response:
        """Make the HTTP request and return it directly.

        Parameters
        ----------
        method : str
            HTTP method verb.
        url : str
            Absolute URL of the target endpoint, including any path and query parameters.
        query_params : str
            Query parameters to pass in the URL.
        headers : Dict
            Headers to attach to the request.
        post_params : Optional[Iterable[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]]]
            Request post form parameters for ``multipart/form-data``.
        body : :obj:`.SerializedType`
            Request body.
        _request_timeout : Union[float, Tuple[float, float], None]
            Timeout setting for the request. If only one number is provided, it is used as a total request timeout.
            It can also be a pair (tuple) of (connection, read) timeouts. This parameter overrides the session-level
            timeout setting.
        """
        rc = self.rest_client
        if not isinstance(rc, httpx.Client):
            raise TypeError("ApiClient requires an httpx.Client instance.")
        url_effective, kw, body_kw = self._prepare_httpx_request_args(
            url, query_params, headers, post_params, body, _request_timeout
        )
        if method == "GET":
            return rc.get(url_effective, **kw)
        if method == "HEAD":
            return rc.head(url_effective, **kw)
        if method == "OPTIONS":
            return rc.request(
                "OPTIONS",
                url_effective,
                **kw,
                **body_kw,
            )
        if method == "POST":
            return rc.post(url_effective, **kw, **body_kw)
        if method == "PUT":
            return rc.put(url_effective, **kw, **body_kw)
        if method == "PATCH":
            return rc.patch(url_effective, **kw, **body_kw)
        if method == "DELETE":
            return rc.request("DELETE", url_effective, **kw, **body_kw)
        raise ValueError(
            "http method must be `GET`, `HEAD`, `OPTIONS`, `POST`, `PATCH`, `PUT`, or `DELETE`."
        )

    @staticmethod
    def parameters_to_tuples(
        params: Union[Dict, List[Tuple]], collection_formats: Optional[Dict[str, str]]
    ) -> List[Tuple[Any, Any]]:
        """Get parameters as a list of tuples, formatting collections.

        Parameters
        ----------
        params : Union[Dict, List[Tuple]]
            Parameters for the request, either a dictionary with a name and value or a list
            of tuples with names and values.
        collection_formats : Dict[str, str]
            Dictionary with a parameter name and collection type specifier.
        """
        new_params: List[Tuple[Any, Any]] = []
        if collection_formats is None:
            collection_formats = {}
        for k, v in params.items() if isinstance(params, dict) else params:
            if k in collection_formats:
                collection_format = collection_formats[k]
                if collection_format == "multi":
                    new_params.extend((k, value) for value in v)
                else:
                    if collection_format == "ssv":
                        delimiter = " "
                    elif collection_format == "tsv":
                        delimiter = "\t"
                    elif collection_format == "pipes":
                        delimiter = "|"
                    else:  # csv is the default
                        delimiter = ","
                    new_params.append((k, delimiter.join(str(value) for value in v)))
            else:
                new_params.append((k, v))
        return new_params

    @staticmethod
    def prepare_post_parameters(
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[
            Mapping[str, Union[str, bytes, IO, Iterable[Union[str, bytes, IO]]]]
        ] = None,
    ) -> Iterable[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]]:
        """Build form parameters.

        This method combines plain form parameters and file parameters into a structure suitable for transmission.

        Parameters
        ----------
        post_params : Optional[List[Tuple[str, Union[str, bytes]]]]
            Plain form parameters.
        files : Optional[Mapping[str, Union[str, bytes, IO, Iterable[Union[str, bytes, IO]]]]]
            File parameters. Each value may be a file path (``str`` or ``bytes``), an open
            file-like object (``IO``), or an iterable of any combination thereof.
        """
        params: List[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]] = []

        if post_params:
            params.extend(post_params)

        if files:
            for parameter, file_entry in files.items():
                if not file_entry:
                    continue
                file_names_or_contents = (
                    file_entry if isinstance(file_entry, list) else [file_entry]
                )
                for file_name_or_content in file_names_or_contents:
                    if hasattr(file_name_or_content, "read"):
                        file_content = cast(IO, file_name_or_content)
                        param = ApiClient._process_file(file_content)
                        params.append((parameter, param))
                    else:
                        file_name = cast(Union[str, bytes], file_name_or_content)
                        with open(file_name, "rb") as f:
                            param = ApiClient._process_file(f)
                            params.append((parameter, param))

        return params

    @staticmethod
    def _process_file(fp: IO) -> Tuple[str, Union[str, bytes], str]:
        filename = os.path.basename(fp.name)
        file_data = fp.read()
        mimetype = mimetypes.guess_type(filename)[0] or "application/octet-stream"
        return filename, file_data, mimetype

    @staticmethod
    def select_header_accept(accepts: Optional[List[str]]) -> Optional[str]:
        """Return a correctly formatted ``Accept`` header value from the provided array of accepted content types.

        Parameters
        ----------
        accepts : List[str], optional
            List of accepted content types.

        Examples
        --------
        >>> ApiClient.select_header_accept(['Application/JSON', 'text/xml'])
        'application/json, text/xml'
        """
        if not accepts:
            return None

        accepts = [accept.lower() for accept in accepts]

        return ", ".join(accepts)

    @staticmethod
    def select_header_content_type(content_types: Optional[List[str]]) -> str:
        """Return the preferred ``Content-Type`` header value from the provided array of valid content types.

        Parameters
        ----------
        content_types : List[str], optional
            List of content types.

        Notes
        -----
        If more than one valid ``Content-Type`` is provided, the first one in the list is used.

        Examples
        --------
        >>> ApiClient.select_header_content_type()
        'application/json'

        >>> ApiClient.select_header_content_type(['text/xml', 'Application/JSON'])
        'text/xml'

        >>> ApiClient.select_header_content_type(['*/*'])
        'application/json'
        """
        if not content_types:
            return "application/json"

        content_types = [content_type.lower() for content_type in content_types]

        if "application/json" in content_types or "*/*" in content_types:
            return "application/json"
        else:
            return content_types[0]

    def __deserialize_file(self, response: httpx.Response) -> str:
        """Deserialize the body to a file.

        This method saves the response body in a file in a temporary folder,
        using the file name from the ``Content-Disposition`` header if provided.

        Parameters
        ----------
        response : httpx.Response
            The API response object to deserialize.
        """
        fd, path = tempfile.mkstemp(dir=self.configuration.temp_folder_path)
        os.close(fd)
        os.remove(path)

        if "Content-Disposition" in response.headers:
            filename_match = re.search(
                r'filename=[\'"]?([^\'"\s]+)[\'"]?',
                response.headers["Content-Disposition"],
            )
            if filename_match is not None:
                filename = filename_match.group(1)
                path = os.path.join(os.path.dirname(path), filename)

        with open(path, "wb") as f:
            f.write(response.content)

        return path

    @staticmethod
    def __deserialize_primitive(
        data: PrimitiveType, klass: Callable[..., PrimitiveType]
    ) -> PrimitiveType:
        """Deserialize to the primitive type.

        Parameters
        ----------
        data : Union[str, int, float, bool, bytes]
            Data to deserialize into the primitive type.
        klass : Type
            Type of target object for deserialization.
        """
        try:
            return klass(data)
        except UnicodeEncodeError:
            return str(data)
        except (ValueError, TypeError):
            return data

    @staticmethod
    def __deserialize_object(value: object) -> object:
        """Return an original value.

        Parameters
        ----------
        value : object
            Generic object that does not match any specific deserialization strategy.
        """
        return value

    @staticmethod
    def __deserialize_date(value: str) -> datetime.date:
        """Deserialize string to ``datetime.date``.

        Parameters
        ----------
        value : str
            String representation of a date object in ISO 8601 format or otherwise.
        """
        try:
            return parse(value).date()
        except ValueError:
            raise ApiException(
                status_code=0,
                reason_phrase=f"Failed to parse `{value}` as date object",
            )

    @staticmethod
    def __deserialize_datetime(value: str) -> datetime.datetime:
        """Deserialize string to ``datetime.datetime``.

        Parameters
        ----------
        value : str
            String representation of the ``datetime`` object in ISO 8601 format.
        """
        try:
            return parse(value)
        except ValueError:
            raise ApiException(
                status_code=0,
                reason_phrase=f"Failed to parse `{value}` as datetime object",
            )

    def __deserialize_model(
        self, data: Union[Dict, str], klass: Type[ModelBase]
    ) -> Union[ModelBase, Dict, str]:
        """Deserialize model representation to model.

        Given a model type and the serialized data, deserialize into an instance of the model class.

        Parameters
        ----------
        data : Union[Dict, str]
            Serialized representation of the model object.
        klass : ModelType
            Type of the model to deserialize.
        """
        if not klass.swagger_types:
            try:
                klass.get_real_child_model(klass(), {})
            except NotImplementedError:
                return data
            except BaseException:
                pass

        kwargs = {}
        if klass.swagger_types is not None:
            for attr, attr_type in klass.swagger_types.items():
                if (
                    data is not None
                    and klass.attribute_map[attr] in data
                    and isinstance(data, (list, dict))
                ):
                    value = data[klass.attribute_map[attr]]
                    kwargs[attr] = self.__deserialize(value, attr_type)

        instance = klass(**kwargs)

        if (
            isinstance(instance, dict)
            and klass.swagger_types is not None
            and isinstance(data, dict)
        ):
            for key, value in data.items():
                if key not in klass.swagger_types:
                    instance[key] = value
        try:
            klass_name = instance.get_real_child_model(data)  # type: ignore[arg-type]
            if klass_name:
                instance = self.__deserialize(data, klass_name)  # type: ignore[assignment]
        except NotImplementedError:
            pass

        return instance


class AsyncApiClient(ApiClient):
    """OpenAPI API client that performs HTTP I/O with :class:`httpx.AsyncClient`.

    Build an async client with :func:`~.create_async_httpx_client_from_session_configuration`
    (optionally passing a finalized sync client to reuse headers, cookies, and auth).

    Notes
    -----
    Use :meth:`acall_api` / :meth:`arequest` and ``await aclose()``, or the asynchronous
    context manager. Synchronous :meth:`~ApiClient.call_api`, :meth:`~ApiClient.request`,
    and :meth:`~ApiClient.close` are disabled and raise :class:`TypeError`.
    """

    def close(self) -> None:
        """Raise :class:`TypeError`; use :meth:`aclose` instead."""
        raise TypeError(
            "AsyncApiClient must be closed with await aclose() or 'async with AsyncApiClient(...)'."
        )

    def __enter__(self) -> NoReturn:
        """Disallow synchronous ``with``; use ``async with``."""
        raise TypeError("Use 'async with AsyncApiClient(...)' instead of synchronous 'with'.")

    def __exit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Disallow synchronous ``with``; use ``async with``."""
        raise TypeError("Use 'async with AsyncApiClient(...)' instead of synchronous 'with'.")

    async def __aenter__(self) -> "AsyncApiClient":
        """Return this client for use in ``async with``."""
        return self

    async def __aexit__(
        self,
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional[TracebackType],
    ) -> None:
        """Close the HTTP client when leaving ``async with``."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying async HTTP client and any distinct auth helper clients."""
        if self._closed:
            return
        self._closed = True
        rc = self.rest_client
        if not isinstance(rc, httpx.AsyncClient):
            raise TypeError("AsyncApiClient requires an httpx.AsyncClient instance.")
        await _aclose_distinct_httpx_auth_clients(rc)
        await rc.aclose()

    def call_api(
        self,
        resource_path: str,
        method: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        header_params: Union[Dict[str, Union[str, int]], None] = None,
        body: Optional[DeserializedType] = None,
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[Mapping[str, Union[str, bytes, IO]]] = None,
        response_type: Optional[str] = None,
        _return_http_data_only: Optional[bool] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
        response_type_map: Optional[Mapping[int, Union[str, None]]] = None,
    ) -> Union[DeserializedType, Tuple[DeserializedType, int, httpx.Headers], None]:
        """Raise :class:`TypeError`; use :meth:`acall_api` instead."""
        raise TypeError("Use await acall_api(...) for async OpenAPI calls.")

    def request(
        self,
        method: str,
        url: str,
        query_params: Optional[str] = None,
        headers: Optional[Dict] = None,
        post_params: Optional[
            Iterable[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]]
        ] = None,
        body: Optional[Any] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
    ) -> httpx.Response:
        """Raise :class:`TypeError`; use :meth:`arequest` instead."""
        raise TypeError("Use await arequest(...) for async HTTP.")

    async def arequest(
        self,
        method: str,
        url: str,
        query_params: Optional[str] = None,
        headers: Optional[Dict] = None,
        post_params: Optional[
            Iterable[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]]
        ] = None,
        body: Optional[Any] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
    ) -> httpx.Response:
        """Make an asynchronous HTTP request and return the response."""
        rc = self.rest_client
        if not isinstance(rc, httpx.AsyncClient):
            raise TypeError("AsyncApiClient requires an httpx.AsyncClient instance.")
        url_effective, kw, body_kw = self._prepare_httpx_request_args(
            url, query_params, headers, post_params, body, _request_timeout
        )
        if method == "GET":
            return await rc.get(url_effective, **kw)
        if method == "HEAD":
            return await rc.head(url_effective, **kw)
        if method == "OPTIONS":
            return await rc.request(
                "OPTIONS",
                url_effective,
                **kw,
                **body_kw,
            )
        if method == "POST":
            return await rc.post(url_effective, **kw, **body_kw)
        if method == "PUT":
            return await rc.put(url_effective, **kw, **body_kw)
        if method == "PATCH":
            return await rc.patch(url_effective, **kw, **body_kw)
        if method == "DELETE":
            return await rc.request("DELETE", url_effective, **kw, **body_kw)
        raise ValueError(
            "http method must be `GET`, `HEAD`, `OPTIONS`, `POST`, `PATCH`, `PUT`, or `DELETE`."
        )

    async def acall_api(
        self,
        resource_path: str,
        method: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        header_params: Union[Dict[str, Union[str, int]], None] = None,
        body: Optional[DeserializedType] = None,
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[Mapping[str, Union[str, bytes, IO]]] = None,
        response_type: Optional[str] = None,
        _return_http_data_only: Optional[bool] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
        response_type_map: Optional[Mapping[int, Union[str, None]]] = None,
    ) -> Union[DeserializedType, Tuple[DeserializedType, int, httpx.Headers], None]:
        """Async counterpart of :meth:`ApiClient.call_api`."""
        return await self.__acall_api(
            resource_path,
            method,
            path_params,
            query_params,
            header_params,
            body,
            post_params,
            files,
            response_type,
            _return_http_data_only,
            collection_formats,
            _request_timeout,
            response_type_map,
        )

    async def __acall_api(
        self,
        resource_path: str,
        method: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        header_params: Union[Dict[str, Union[str, int]], None] = None,
        body: Optional[Any] = None,
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[
            Mapping[str, Union[str, bytes, IO, Iterable[Union[str, bytes, IO]]]]
        ] = None,
        response_type: Optional[str] = None,
        _return_http_data_only: Optional[bool] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
        response_type_map: Optional[Mapping[int, Union[str, None]]] = None,
    ) -> Union[DeserializedType, Tuple[DeserializedType, int, httpx.Headers], None]:
        parts = self._build_call_request_parts(
            resource_path,
            method,
            path_params,
            query_params,
            header_params,
            body,
            post_params,
            files,
            collection_formats,
            _request_timeout,
        )
        response_data = await self.arequest(
            parts.method,
            parts.url,
            query_params=parts.query_params_str,
            headers=parts.header_params,
            post_params=parts.post_params,
            body=parts.body,
            _request_timeout=parts.request_timeout,
        )
        return self._finish_call_api(
            response_data, response_type, _return_http_data_only, response_type_map
        )
