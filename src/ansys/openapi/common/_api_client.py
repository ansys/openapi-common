import datetime
import json
import mimetypes
import os
import re
import tempfile
from types import ModuleType
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    IO,
    Iterable,
    Mapping,
    Sequence,
)
from urllib.parse import quote

import requests
from dateutil.parser import parse
from requests.structures import CaseInsensitiveDict

from ._base import (
    ApiClientBase,
    DeserializedType,
    ModelBase,
    PrimitiveType,
    SerializedType,
)
from ._exceptions import ApiException
from ._util import SessionConfiguration, handle_response


# noinspection DuplicatedCode
class ApiClient(ApiClientBase):
    """Provides a generic API client for OpenAPI client library builds.

    This client handles client-server communication and is invariant across
    implementations. Specifics of the methods and models for each application are
    generated from OpenAPI templates and are responsible for interfacing with the
    public API exposed by the client.

    Parameters
    ----------
    session : requests.Session
        Base session object that the API client is to use.
    api_url : str
        Base URL for the API. All generated endpoint URLs are relative to this address.
    configuration : SessionConfiguration
        Configuration options for the API client.

    Examples
    --------
    >>> client = ApiClient(requests.Session(),
    ...                    'http://my-api.com/API/v1.svc',
    ...                    SessionConfiguration())
    ... <ApiClient url: http://my-api.com/API/v1.svc>

    For testing purposes, it is common to configure an API with a self-signed certificate. By default, the
    :class:`ApiClient` class will not trust self-signed SSL certificates. To allow this, pass a path to the
    root certificate to the :class:`SessionConfiguration` object. For more configuration examples, see
    :class:`SessionConfiguration`.

    >>> session_config = SessionConfiguration(cert_store_path='./self-signed-cert.pem')
    ... ssl_client = ApiClient(requests.Session(),
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
        session: requests.Session,
        api_url: str,
        configuration: SessionConfiguration,
    ):
        self.models: Dict[str, Type[ModelBase]] = {}
        self.api_url = api_url
        self.rest_client = session
        self.configuration = configuration

    def __repr__(self) -> str:
        return f"<ApiClient url: {self.api_url}>"

    def setup_client(self, models: ModuleType) -> None:
        """Set up the client for use and register models for serialization and deserialization. This step must be
        completed prior to using the :class:`ApiClient` class.

        Parameters
        ----------
        models : ModuleType
            Module containing models generated by the Swagger code generator tool.

        Examples
        --------
        >>> client = ApiClient(requests.Session(),
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... import ApiModels as model_module
        ... client.setup_client(model_module)
        """
        self.models = models.__dict__

    def __call_api(
        self,
        resource_path: str,
        method: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        header_params: Union[Dict[str, Union[str, int]], None] = None,
        body: Optional[Any] = None,
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[Mapping[str, Union[str, bytes, IO]]] = None,
        response_type: Optional[str] = None,
        _return_http_data_only: Optional[bool] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _preload_content: bool = True,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
        response_type_map: Optional[Dict[int, Union[str, None]]] = None,
    ) -> Union[requests.Response, DeserializedType, None]:
        # header parameters
        header_params = header_params or {}
        if header_params:
            header_params_sanitized = self.sanitize_for_serialization(header_params)
            header_params = dict(
                self.parameters_to_tuples(header_params_sanitized, collection_formats)
            )

        # path parameters
        if path_params:
            resource_path = self.__handle_path_params(
                resource_path, path_params, collection_formats
            )

        # query parameters
        query_params_str = ""
        if query_params:
            query_params_str = self.__handle_query_params(
                query_params, collection_formats
            )

        # post parameters
        if post_params or files:
            post_param_tuples = self.prepare_post_parameters(post_params, files)
            sanitized_post_params = self.sanitize_for_serialization(post_param_tuples)
            post_params = self.parameters_to_tuples(
                sanitized_post_params, collection_formats
            )

        # body
        if body:
            body = self.sanitize_for_serialization(body)
            if isinstance(body, (list, dict)):
                body = json.dumps(body).encode("utf8")

        # request url
        url = self.api_url + resource_path

        # perform request and return response
        response_data = self.request(
            method,
            url,
            query_params=query_params_str,
            headers=header_params,
            post_params=post_params,
            body=body,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
        )

        self.last_response = response_data

        return_data: Union[requests.Response, DeserializedType, None] = response_data
        if _preload_content:
            _response_type = response_type
            if response_type_map is not None:
                _response_type = response_type_map.get(response_data.status_code, None)

            return_data = self.deserialize(response_data, _response_type)

        if _return_http_data_only:
            return return_data
        else:
            return return_data, response_data.status_code, response_data.headers

    def __handle_path_params(
        self,
        resource_path: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None],
        collection_formats: Optional[Dict[str, str]],
    ) -> str:
        path_params_sanitized = self.sanitize_for_serialization(path_params)
        path_params_tuples = self.parameters_to_tuples(
            path_params_sanitized, collection_formats
        )
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
        query_params_tuples = self.parameters_to_tuples(
            query_params_sanitized, collection_formats
        )
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
        >>> client = ApiClient(requests.Session(),
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... client.sanitize_for_serialization({'key': 'value'})
        {'key': 'value'}

        >>> client = ApiClient(requests.Session(),
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

        if isinstance(obj, dict):
            obj_dict = obj
        else:
            obj_dict = {
                obj.attribute_map[attr]: getattr(obj, attr)
                for attr in obj.swagger_types
                if getattr(obj, attr) is not None
            }

        return {
            key: self.sanitize_for_serialization(val) for key, val in obj_dict.items()
        }

    def deserialize(
        self, response: requests.Response, response_type: Optional[str]
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
        response : requests.Response
            Response object received from the API.
        response_type : str
            String name of the class represented.

        Examples
        --------
        >>> client = ApiClient(requests.Session(),
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... api_response = requests.Response()
        ... api_response._content = b"{'key': 'value'}"
        ... client.deserialize(api_response, 'Dict[str, str]]')
        {'key': 'value'}

        >>> client = ApiClient(requests.Session(),
        ...                    'http://my-api.com/API/v1.svc',
        ...                    SessionConfiguration())
        ... api_response = requests.Response()
        ... api_response._content = b"'2015-10-21T10:05:10'"
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
        """

        if data is None:
            return None

        list_match = self.LIST_MATCH_REGEX.match(klass_name)
        if list_match is not None:
            assert isinstance(data, list)
            sub_kls = list_match.group(1)
            return [self.__deserialize(sub_data, sub_kls) for sub_data in data]

        dict_match = self.DICT_MATCH_REGEX.match(klass_name)
        if dict_match is not None:
            assert isinstance(data, dict)
            sub_kls = dict_match.group(2)
            return {k: self.__deserialize(v, sub_kls) for k, v in data.items()}

        if klass_name in self.NATIVE_TYPES_MAPPING:
            klass = self.NATIVE_TYPES_MAPPING[klass_name]
        else:
            klass = self.models[klass_name]

        if klass in self.PRIMITIVE_TYPES:
            assert isinstance(data, (str, int, float, bool, bytes))
            return self.__deserialize_primitive(data, klass)
        elif klass == datetime.date:
            assert isinstance(data, str)
            return self.__deserialize_date(data)
        elif klass == datetime.datetime:
            assert isinstance(data, str)
            return self.__deserialize_datetime(data)
        else:
            assert isinstance(data, (dict, str))
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
        _preload_content: bool = True,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
        response_type_map: Optional[Dict[int, Union[str, None]]] = None,
    ) -> Union[requests.Response, DeserializedType, None]:
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
        _preload_content : bool, optional
            Whether to return the underlying response without reading or decoding response data. The default
            is ``True``, in which case response data is read or decoded. If ``False``, response data is not
            read or decoded.
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
            _preload_content,
            _request_timeout,
            response_type_map,
        )

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
        _preload_content: bool = True,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
    ) -> requests.Response:
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
        _preload_content : bool, optional
            Whether to return the underlying response without reading or decoding response data. The default
            is ``True``, in which case the response data is read or decoded.  If ``False``, the response
            data is not read or decoded.
        _request_timeout : Union[float, Tuple[float, float], None]
            Timeout setting for the request. If only one number is provided, it is used as a total request timeout.
            It can also be a pair (tuple) of (connection, read) timeouts. This parameter overrides the session-level
            timeout setting.
        """

        if method == "GET":
            return handle_response(
                self.rest_client.get(
                    url,
                    params=query_params,
                    stream=_preload_content,
                    timeout=_request_timeout,
                    headers=headers,
                )
            )
        elif method == "HEAD":
            return handle_response(
                self.rest_client.head(
                    url,
                    params=query_params,
                    stream=_preload_content,
                    timeout=_request_timeout,
                    headers=headers,
                )
            )
        elif method == "OPTIONS":
            return handle_response(
                self.rest_client.options(
                    url,
                    params=query_params,
                    headers=headers,
                    files=post_params,
                    stream=_preload_content,
                    timeout=_request_timeout,
                    data=body,
                )
            )
        elif method == "POST":
            return handle_response(
                self.rest_client.post(
                    url,
                    params=query_params,
                    headers=headers,
                    files=post_params,
                    stream=_preload_content,
                    timeout=_request_timeout,
                    data=body,
                )
            )
        elif method == "PUT":
            return handle_response(
                self.rest_client.put(
                    url,
                    params=query_params,
                    headers=headers,
                    files=post_params,
                    stream=_preload_content,
                    timeout=_request_timeout,
                    data=body,
                )
            )
        elif method == "PATCH":
            return handle_response(
                self.rest_client.patch(
                    url,
                    params=query_params,
                    headers=headers,
                    files=post_params,
                    stream=_preload_content,
                    timeout=_request_timeout,
                    data=body,
                )
            )
        elif method == "DELETE":
            return handle_response(
                self.rest_client.delete(
                    url,
                    params=query_params,
                    headers=headers,
                    stream=_preload_content,
                    timeout=_request_timeout,
                    data=body,
                )
            )
        else:
            raise ValueError(
                "http method must be `GET`, `HEAD`, `OPTIONS`,"
                " `POST`, `PATCH`, `PUT`, or `DELETE`."
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
        files: Optional[Mapping[str, Union[str, bytes, IO]]] = None,
    ) -> Iterable[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]]:
        """Build form parameters.

        This method combines plain form parameters and file parameters into a structure suitable for transmission.

        Parameters
        ----------
        post_params : Optional[List[Tuple[str, Union[str, bytes]]]]
            Plain form parameters.
        files : Optional[Mapping[str, Union[str, bytes]]]
            File parameters.
        """
        params: List[
            Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]
        ] = []

        if post_params:
            params.extend(post_params)

        if files:
            for parameter, file_entry in files.items():
                if not file_entry:
                    continue
                file_names = (
                    file_entry if isinstance(file_entry, list) else [file_entry]
                )
                for file_name in file_names:
                    if isinstance(file_name, IO):
                        param = ApiClient._process_file(file_name)
                        params.append((parameter, param))
                    else:
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

    def __deserialize_file(self, response: requests.Response) -> str:
        """Deserialize the body to a file.

        This method saves the response body in a file in a temporary folder,
        using the file name from the ``Content-Disposition`` header if provided.

        Parameters
        ----------
        response : requests.Response
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
        data: PrimitiveType, klass: Callable[[PrimitiveType], PrimitiveType]
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
            klass_name = instance.get_real_child_model(data)
            if klass_name:
                instance = self.__deserialize(data, klass_name)  # type: ignore[assignment]
        except NotImplementedError:
            pass

        return instance
