import abc
import datetime
import pprint
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

PrimitiveType = Union[float, bool, bytes, str, int]
DeserializedType = Union[
    None,
    PrimitiveType,
    datetime.datetime,
    datetime.date,
    Enum,
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

    def to_dict(self) -> Dict:
        """Returns the model properties as a dict

        Returns
        -------
        Dict
            Dictionary indexed by property name containing all the model properties
        """
        result = {}

        for attr in self.swagger_types.keys():
            value = getattr(self, attr)
            if isinstance(value, list):
                result[attr] = [
                    item.to_dict() if hasattr(item, "to_dict") else item
                    for item in value
                ]
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = {
                    item_key: (
                        item_value.to_dict()
                        if hasattr(item_value, "to_dict")
                        else item_value
                    )
                    for item_key, item_value in value.items()
                }  # type: ignore
            elif isinstance(value, Enum):
                result[attr] = value.value
            else:
                result[attr] = value
        if isinstance(self, dict):
            for key, value in self.items():
                result[key] = value

        return result

    def to_str(self) -> str:
        """Returns the string representation of the model

        Returns
        -------
        str
            String representation of the model as a dictionary
        """
        return pprint.pformat(self.to_dict())

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
        post_params: Optional[List[Tuple[str, Union[str, bytes]]]] = None,
        files: Optional[Dict[str, str]] = None,
        response_type: Optional[str] = None,
        _return_http_data_only: Optional[bool] = None,
        collection_formats: Optional[Dict[str, str]] = None,
        _preload_content: bool = True,
        _request_timeout: Union[float, Tuple[float, float], None] = None,
        response_type_map: Optional[Dict[int, Union[str, None]]] = None,
    ) -> Union[requests.Response, DeserializedType, None]:
        ...
