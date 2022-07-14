import abc
import datetime
from typing import Union, List, Tuple, Dict, Any, Optional

import requests

PrimitiveType = Union[float, bool, bytes, str, int]
DeserializedType = Union[
    None,
    PrimitiveType,
    datetime.datetime,
    datetime.date,
    List,
    Tuple,
    Dict,
    "ModelBase",
]
SerializedType = Union[None, PrimitiveType, List, Tuple, Dict]


class ModelBase(metaclass=abc.ABCMeta):
    """Provides a base class defining the interface that API clients will use to interact with generated client
    libraries."""

    swagger_types: Dict[str, str]
    attribute_map: Dict[str, str]

    @abc.abstractmethod
    def __init__(self, *args: Any, **kwargs: Any) -> None:
        ...

    @abc.abstractmethod
    def to_dict(self) -> Dict[str, DeserializedType]:
        ...

    @abc.abstractmethod
    def to_str(self) -> str:
        ...

    def get_real_child_model(self, data: Union[Dict, str]) -> str:
        """Classes with discriminators will override this method and may change the method signature."""
        raise NotImplementedError()


class ApiBase(metaclass=abc.ABCMeta):
    """Provides a base class defining the interface that API clients will use to interact with generated client
    libraries."""

    def __init__(self, api_client: "ApiClientBase") -> None:
        self.api_client = api_client


class ApiClientBase(metaclass=abc.ABCMeta):
    """Provides a base class defining the interface that generated client libraries depend upon."""

    @staticmethod
    @abc.abstractmethod
    def select_header_accept(accepts: Optional[List[str]]) -> Optional[str]:
        ...

    @staticmethod
    @abc.abstractmethod
    def select_header_content_type(content_types: Optional[List[str]]) -> str:
        ...

    @abc.abstractmethod
    def call_api(
        self,
        resource_path: str,
        method: str,
        path_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        query_params: Union[Dict[str, Union[str, int]], List[Tuple], None] = None,
        header_params: Union[Dict[str, Union[str, int]], None] = None,
        body: Optional[DeserializedType] = None,
        post_params: Optional[List[Tuple]] = None,
        files: Optional[Dict[str, str]] = None,
        response_type: Optional[str] = None,
        _return_http_data_only: Optional[bool] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _preload_content: bool = True,
        _request_timeout: Union[float, Tuple[float], None] = None,
    ) -> Union[requests.Response, DeserializedType, None]:
        ...
