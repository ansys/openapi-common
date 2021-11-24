import datetime
import mimetypes
import json
import os
import re
import tempfile
from typing import Dict, Union, List, Tuple, Type, Optional, cast

from urllib.parse import quote

import requests
from requests.structures import CaseInsensitiveDict

from ._util import SessionConfiguration, ModelType, handle_response
from ._exceptions import ApiException
from types import ModuleType


DeserializedType = Union[
    None,
    str,
    int,
    float,
    bool,
    bytes,
    datetime.datetime,
    datetime.date,
    List,
    Tuple,
    Dict,
    ModelType,
]
SerializedType = Union[None, str, int, float, bool, bytes, List, Tuple, Dict]


# noinspection DuplicatedCode
class ApiClient:
    """Generic API client for OpenAPI client library builds.

    This client handles the client-server communication, and is invariant across
    implementations. Specifics of the methods and models for each application are
    generated from OpenAPI templates and are responsible for interfacing with the
    public API exposed by the client.

    Parameters
    ----------
    session : requests.Session
        Base session object that the API Client will use
    api_url : str
        Base URL for the API, all generated endpoint urls are relative to this address
    configuration : SessionConfiguration
        Configuration options for the Api Client
    """

    PRIMITIVE_TYPES = (float, bool, bytes, str, int)
    NATIVE_TYPES_MAPPING = {
        "int": int,
        "float": float,
        "str": str,
        "bool": bool,
        "date": datetime.date,
        "datetime": datetime.datetime,
    }

    def __init__(
        self,
        session: requests.Session,
        api_url: str,
        configuration: SessionConfiguration,
    ):
        """Create a new instance of the ApiClient class.

        Examples
        --------
        >>> ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
        <ApiClient url: http://my-api.com/API/v1.svc>

        For testing purposes it is common to configure an API with a self-signed certificate, by default the ApiClient
        will not trust self-signed SSL certificates. To allow this, pass a path to the root certificate to the
        SessionConfiguration object. For more examples of configuration see the :obj:`SessionConfiguration`
        documentation.

        >>> session_config = SessionConfiguration(cert_store_path='./self-signed-cert.pem')
        ... ssl_client = ApiClient(requests.Session(), 'https://secure-api/API/v1.svc', session_config)
        ... ssl_client
        <ApiClient url: https://secure-api/API/v1.svc>
        """
        self.models: Dict[str, ModelType] = {}
        self.api_url = api_url
        self.rest_client = session
        self.default_headers: CaseInsensitiveDict = CaseInsensitiveDict()
        self.default_headers["User-Agent"] = "Swagger-Codegen/1.0.0/python"
        self.configuration = configuration

    def __repr__(self) -> str:
        return f"<ApiClient url: {self.api_url}>"

    def setup_client(self, models: ModuleType) -> None:
        """Setup the client for use, registers models for serialization and deserialization. This step must be completed
        prior to using the ApiClient.

        Parameters
        ----------
        models : ModuleType
            Module containing models generated by the Swagger code generator tool, see {} for more information

        Examples
        --------
        >>> client = ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
        ... import ApiModels as model_module
        ... client.setup_client(model_module)
        """
        self.models = models.__dict__

    @property
    def user_agent(self):
        """The user agent reported to the API server in the "User-Agent" header.

        Some APIs will behave differently for different client applications, change this if your API requires different
        behaviour.

        Examples
        --------
        >>> client = ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
        ... client.user_agent
        'Swagger-Codegen/1.0.0/python'

        Change the user-agent string to impersonate a fairly recent Mozilla Firefox browser

        >>> client = ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
        ... client.user_agent = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'

        Notes
        -----
        The behaviour of the OIDC login process is not governed by the User-Agent string, it is not possible to use a
        different login flow by changing this value.
        """
        return self.default_headers["User-Agent"]

    @user_agent.setter
    def user_agent(self, value):
        self.default_headers["User-Agent"] = value

    def set_default_header(self, header_name, header_value):
        """Set a default value for a header on all requests

        Certain headers will be overwritten by the API when sending requests, but default values for others can be set
        and will be respected, for example if your API server is configured to require non OIDC tokens for
        authentication

        >>> client = ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
        ... client.set_default_header('Authorization', 'my-token-value')

        Notes
        -----
        Some headers will always be overwritten, and some may be depending on the API endpoint requested. As a guide the
        following headers will always be ignored and overwritten:

        - Accept
        - Content-Type

        The `Authorization` header may be overwritten depending on what, if any, authentication scheme is provided for
        the requests Session.
        """
        self.default_headers[header_name] = header_value

    def __call_api(
        self,
        resource_path,
        method,
        path_params=None,
        query_params=None,
        header_params=None,
        body=None,
        post_params=None,
        files=None,
        response_type=None,
        _return_http_data_only=None,
        collection_formats=None,
        _preload_content=True,
        _request_timeout=None,
    ):

        # header parameters
        header_params = header_params or {}
        header_params.update(self.default_headers)
        if header_params:
            header_params = self.sanitize_for_serialization(header_params)
            header_params = dict(
                self.parameters_to_tuples(header_params, collection_formats)
            )

        # path parameters
        if path_params:
            path_params = self.sanitize_for_serialization(path_params)
            path_params = self.parameters_to_tuples(path_params, collection_formats)
            for k, v in path_params:
                # specified safe chars, encode everything
                resource_path = resource_path.replace(
                    f"{k}",
                    quote(str(v), safe=self.configuration.safe_chars_for_path_param),
                )

        # query parameters
        if query_params:
            query_params = self.sanitize_for_serialization(query_params)
            query_params = self.parameters_to_tuples(query_params, collection_formats)
            query_params = "&".join(["=".join(param) for param in query_params])

        # post parameters
        if post_params or files:
            post_params = self.prepare_post_parameters(post_params, files)
            post_params = self.sanitize_for_serialization(post_params)
            post_params = self.parameters_to_tuples(post_params, collection_formats)

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
            query_params=query_params,
            headers=header_params,
            post_params=post_params,
            body=body,
            _preload_content=_preload_content,
            _request_timeout=_request_timeout,
        )

        self.last_response = response_data

        return_data = response_data
        if _preload_content:
            # deserialize response data
            if response_type:
                return_data = self.deserialize(response_data, response_type)
            else:
                return_data = None

        if _return_http_data_only:
            return return_data
        else:
            return return_data, response_data.status_code, response_data.headers

    def sanitize_for_serialization(self, obj: DeserializedType) -> SerializedType:
        """Builds a JSON POST object.

        Based on the object type, return the sanitized JSON representation to be sent to the server.

        If obj is None, return None.
        If obj is str, int, float, bool, return directly.
        If obj is datetime.datetime, datetime.date convert to string in iso8601 format.
        If obj is list, sanitize each element in the list.
        If obj is tuple, sanitize each element in the tuple.
        If obj is dict, return the dict.
        If obj is an OpenAPI model, return the properties dict.

        Parameters
        ----------
        obj : DeserializedType
            The data to be sanitized and serialized.

        Returns
        -------
        The serialized form of data.

        Examples
        --------
        >>> client = ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
        ... client.sanitize_for_serialization({'key': 'value'})
        {'key': 'value'}

        >>> client = ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
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
        self, response: requests.Response, response_type: Union[str, Type]
    ) -> DeserializedType:
        """Deserializes response into an object.

        Based on the type of response, creates the appropriate object for use.

        For responses that are in JSON format, process the response and return it.

        If response_type is "file", save the content to a temporary file and return the file name.
        If response_type is datetime.date or datetime.datetime, parse the string and return the datetime object.
        If response_type is list, recursively deserialize the list contents.
        If response_type is dict, recursively deserialize the dictionary keys and values.
        If response_type is an OpenAPI model, return the model object.

        Parameters
        ----------
        response : requests.Response
            The response object received from the API
        response_type : Union[str, Type]
            Either the string name of the class represented, or the type

        Returns
        -------
        The deserialized form of the response object.

        Examples
        --------
        >>> client = ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
        ... api_response = requests.Response()
        ... api_response._content = b"{'key': 'value'}"
        ... client.deserialize(api_response, 'Dict[str, str]]')
        {'key': 'value'}

        >>> client = ApiClient(requests.Session(), 'http://my-api.com/API/v1.svc', SessionConfiguration())
        ... api_response = requests.Response()
        ... api_response._content = b"'2015-10-21T10:05:10'"
        ... client.deserialize(api_response, 'datetime.datetime')
        datetime.datetime(2015, 10, 21, 10, 5, 10)
        """

        if response_type == "file":
            return self.__deserialize_file(response)

        try:
            data = response.json()
        except ValueError:
            if response.headers["Content-Type"] not in ["application/octet-stream"]:
                data = response.text
            else:
                # todo: This _probably_ ought not to happen, certainly it will fail at the moment...
                data = response.content

        return self.__deserialize(data, response_type)

    def __deserialize(
        self, data: SerializedType, klass: Union[str, Type]
    ) -> DeserializedType:
        """Deserializes dict, list, str into an object.

        Parameters
        ----------
        data : Union[Dict, List, str]
            Response data to be deserialized.
        klass : Union[str, Type]
            Type of object the data should be deserialized into, one of:

            * String class name.
            * String Type definition for list or dictionary.
            * Type.

        Returns
        -------
        Deserialized form of response data.
        """

        if data is None:
            return None

        if isinstance(klass, str):
            list_match = re.match(r"list\[(.*)]", klass)
            if list_match is not None:
                assert isinstance(data, list)
                sub_kls = list_match.group(1)
                return [self.__deserialize(sub_data, sub_kls) for sub_data in data]

            dict_match = re.match(r"dict\(([^,]*), (.*)\)", klass)
            if dict_match is not None:
                assert isinstance(data, dict)
                sub_kls = dict_match.group(2)
                return {k: self.__deserialize(v, sub_kls) for k, v in data.items()}

            if klass in self.NATIVE_TYPES_MAPPING:
                klass = self.NATIVE_TYPES_MAPPING[klass]
            else:
                klass = self.models[klass]

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
            assert isinstance(data, (dict, list))
            klass_cast = cast(ModelType, klass)
            return self.__deserialize_model(data, klass_cast)

    def call_api(
        self,
        resource_path: str,
        method: str,
        path_params=None,
        query_params=None,
        header_params=None,
        body=None,
        post_params=None,
        files: Dict[str, str] = None,
        response_type: Union[str, Type] = None,
        _return_http_data_only: bool = None,
        collection_formats: Dict[str, str] = None,
        _preload_content: bool = True,
        _request_timeout: Union[float, Tuple[float]] = None,
    ) -> DeserializedType:
        """Makes the HTTP request (synchronous) and returns deserialized data.

        Parameters
        ----------
        resource_path : str
            Path to method endpoint, relative to base url.
        method : str
            HTTP method verb to call.
        path_params : Dict[str, Union[str, int, float]]
            Path parameters to pass in the url.
        query_params :
            Query parameters to pass in the url.
        header_params :
            Header parameters to be placed in the request header.
        body :
            Request body.
        post_params : dict
            Request post form parameters, for `application/x-www-form-urlencoded`, `multipart/form-data`.
        response_type :
            Expected response data type.
        files : Dict[str, str]
            Dictionary of filename and path for `multipart/form-data`.
        _return_http_data_only : bool, default False
            Return response data without head status code and headers.
        collection_formats : Dict[str, str]
            Collection format name for path, query, header, and post parameters. Maps parameter name to collection type.
        _preload_content : bool, default True
            if False, the underlying response object will be returned without reading/decoding response data.
        _request_timeout : Union[float, Tuple[float]]
            Timeout setting for this request. If one number provided, it will be total request timeout. It can also be a
            pair (tuple) of (connection, read) timeouts. Overrides the session level timeout setting.

        Returns
        -------
        The deserialized response object.
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
        )

    def request(
        self,
        method,
        url,
        query_params=None,
        headers=None,
        post_params=None,
        body=None,
        _preload_content=True,
        _request_timeout=None,
    ):
        """Makes the HTTP request and returns it directly.

        Parameters
        ----------
        method : str
            HTTP method verb to call.
        url : str
            Absolute URL of target endpoint, including any path and query parameters.
        query_params :
            Query parameters to pass in the url.
        headers :
            Headers to be attached to the request.
        post_params : dict
            Request post form parameters, for `application/x-www-form-urlencoded`, `multipart/form-data`.
        body :
            Request body.
        _preload_content : bool, default True
            if False, the underlying response object will be returned without reading/decoding response data.
        _request_timeout : Union[float, Tuple[float]]
            Timeout setting for this request. If one number provided, it will be total request timeout. It can also be a
            pair (tuple) of (connection, read) timeouts. Overrides the session level timeout setting.

        Returns
        -------
        The response object received from the API endpoint.
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
                " `POST`, `PATCH`, `PUT` or `DELETE`."
            )

    @staticmethod
    def parameters_to_tuples(
        params: Union[Dict, List[Tuple]], collection_formats: Optional[Dict[str, str]]
    ) -> List[Tuple]:
        """Get parameters as list of tuples, formatting collections.

        Parameters
        ----------
        params : Union[Dict, List[Tuple]]
            Parameters for the request, either a dictionary with name and value, or a list of tuples with names and
            values.
        collection_formats : Dict[str, str]
            Dictionary with parameter name and collection type specifier.

        Returns
        -------
        Parameters as list of tuples, where collections are formatted as specified.
        """

        new_params = []  # type: List[Tuple]
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
        post_params: List[Tuple] = None, files: Dict[str, Union[str, List[str]]] = None
    ) -> List[Tuple]:
        """Builds form parameters.

        Combines plain form parameters with file parameters into a structure suitable for transmission

        Parameters
        ----------
        post_params : List[Tuple]
            Plain form parameters.
        files : Dict[str, Union[str, List[str]]]
            File parameters.

        Returns
        -------
        Form parameters with file name, contents and mime-type.
        """
        params = []

        if post_params:
            params = post_params

        if files:
            for k, v in files.items():
                if not v:
                    continue
                file_names = v if isinstance(v, list) else [v]
                for n in file_names:
                    with open(n, "rb") as f:
                        filename = os.path.basename(f.name)
                        file_data = f.read()
                        mimetype = (
                            mimetypes.guess_type(filename)[0]
                            or "application/octet-stream"
                        )
                        params.append((k, (filename, file_data, mimetype)))

        return params

    @staticmethod
    def select_header_accept(accepts: Optional[List[str]]) -> Optional[str]:
        """Returns `Accept` based on an array of accepts provided.

        Parameters
        ----------
        accepts : Optional[List[str]]
            List of accepted content types.

        Returns
        -------
        Joined list of accepted content types, if any, separated by commas.

        Examples
        --------
        >>> ApiClient.select_header_accept(['Application/JSON', 'text/xml'])
        'application/json, text/xml'
        """
        if not accepts:
            return None

        accepts = [x.lower() for x in accepts]

        return ", ".join(accepts)

    @staticmethod
    def select_header_content_type(content_types: Optional[List[str]]) -> str:
        """Returns `Content-Type` based on an array of content_types provided.

        Parameters
        ----------
        content_types : Optional[List[str]]
            List of content types.

        Returns
        -------
        Content type to use, default 'application/json'.

        Examples
        --------
        >>> ApiClient.select_header_content_type()
        'application/json'

        >>> ApiClient.select_header_content_type(['text/xml', 'Application/JSON'])
        'text/xml'

        >>> ApiClient.select_header_content_type(['*/*'])
        'application/json'

        Notes
        -----
        If more than one valid Content-Type is provided then the first one will be used.
        """
        if not content_types:
            return "application/json"

        content_types = [x.lower() for x in content_types]

        if "application/json" in content_types or "*/*" in content_types:
            return "application/json"
        else:
            return content_types[0]

    def __deserialize_file(self, response: requests.Response) -> str:
        """Deserializes body to file

        Saves response body into a file in a temporary folder,
        using the filename from the `Content-Disposition` header if provided.

        Parameters
        ----------
        response : requests.Response
            The API response object to be deserialized.

        Returns
        -------
        File path to temporary file location.
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
        data: Union[str, int, float, bool, bytes], klass: Type
    ) -> Union[int, float, str, bool, bytes]:
        """Deserializes to primitive type.

        Parameters
        ----------
        data : Union[str, int, float, bool, bytes]
            Data to be deserialized into primitive type.
        klass : Type
            Type of target object for deserialization.

        Returns
        -------
        Primitive type of response.
        """
        try:
            return klass(data)
        except UnicodeEncodeError:
            return str(data)
        except (ValueError, TypeError):
            return data

    @staticmethod
    def __deserialize_object(value: object) -> object:
        """Return a original value.

        Parameters
        ----------
        value : object
            A general object that does not match any specific deserialization strategy.

        Returns
        -------
        The original object.
        """
        return value

    @staticmethod
    def __deserialize_date(value):
        """Deserializes string to date.

        Parameters
        ----------
        value : str
            String representation of a date object in ISO 8601 format or otherwise.

        Returns
        -------
        Datetime object representing the specified date.
        """
        try:
            from dateutil.parser import parse

            return parse(value).date()
        except ValueError:
            raise ApiException(
                status_code=0,
                reason_phrase=f"Failed to parse `{value}` as date object",
            )

    @staticmethod
    def __deserialize_datetime(value: str) -> datetime.datetime:
        """Deserializes string to datetime.

        Parameters
        ----------
        value : str
            String representation of the datetime object in ISO 8601 format.

        Returns
        -------
        Datetime object representing the specified date and time.
        """
        try:
            from dateutil.parser import parse

            return parse(value)
        except ValueError:
            raise ApiException(
                status_code=0,
                reason_phrase=f"Failed to parse `{value}` as datetime object",
            )

    @staticmethod
    def __hasattr(object_, name):
        return name in object_.__class__.__dict__

    def __deserialize_model(
        self, data: Union[Dict, List], klass: ModelType
    ) -> Union[ModelType, Dict, List]:
        """Deserializes list or dict to model.

        Given a model type and the serialized data, deserialize into an instance of the model class.

        Parameters
        ----------
        data : Union[Dict, List]
            Serialized representation of the model object.
        klass : ModelType
            Type of the model to be deserialized.

        Returns
        -------
        Instance of the model class if it's a valid Model, otherwise return data as-is.
        """

        if not klass.swagger_types and not self.__hasattr(
            klass, "get_real_child_model"
        ):
            return data

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
        if self.__hasattr(instance, "get_real_child_model"):
            klass_name = instance.get_real_child_model(data)
            if klass_name:
                instance = self.__deserialize(data, klass_name)
        return instance
