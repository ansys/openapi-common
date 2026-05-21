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

import abc
import datetime
from enum import Enum
import pprint
from typing import Any, Literal, Mapping, TypeAlias, Union

import httpx

PrimitiveType: TypeAlias = float | bool | bytes | str | int
DeserializedType: TypeAlias = Union[
    None,
    PrimitiveType,
    datetime.datetime,
    datetime.date,
    Enum,
    list[Any],
    tuple[Any, ...],
    dict[str, Any],
    "ModelBase",
]
SerializedType: TypeAlias = None | PrimitiveType | list[Any] | tuple[Any, ...] | dict[str, Any]


class ModelBase(metaclass=abc.ABCMeta):
    """Provides a base class for all generated models."""

    swagger_types: dict[str, str]
    attribute_map: dict[str, str]

    @abc.abstractmethod
    def __init__(self, *args: Any, **kwargs: Any) -> None: ...

    def to_dict(self) -> dict[str, Any]:
        """Return the model properties as a dict.

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
                    item.to_dict() if hasattr(item, "to_dict") else item for item in value
                ]
            elif hasattr(value, "to_dict"):
                result[attr] = value.to_dict()
            elif isinstance(value, dict):
                result[attr] = {
                    item_key: (
                        item_value.to_dict() if hasattr(item_value, "to_dict") else item_value
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
        """Return the string representation of the model.

        Returns
        -------
        str
            String representation of the model as a dictionary
        """
        return pprint.pformat(self.to_dict())

    def get_real_child_model(self, data: dict[str, str]) -> str:
        """Classes with discriminators will override this method and may change the method signature."""
        raise NotImplementedError()


class ApiBase(metaclass=abc.ABCMeta):
    """Provides a base class for all generated API classes."""

    def __init__(self, api_client: "ApiClientBase") -> None:
        self.api_client = api_client


class ApiClientBase(metaclass=abc.ABCMeta):
    """Provides a base class defining the interface that generated client libraries depend upon."""

    @staticmethod
    @abc.abstractmethod
    def select_header_accept(accepts: list[str] | None) -> str | None:
        """Provide method signature for determining header priority."""

    @staticmethod
    @abc.abstractmethod
    def select_header_content_type(content_types: list[str] | None) -> str:
        """Provide method signature for determining header priority."""

    @abc.abstractmethod
    def call_api(
        self,
        resource_path: str,
        method: str,
        path_params: dict[str, str | int] | list[tuple[Any, ...]] | None = None,
        query_params: dict[str, str | int] | list[tuple[Any, ...]] | None = None,
        header_params: dict[str, str | int] | None = None,
        body: DeserializedType | None = None,
        post_params: list[tuple[str, str | bytes]] | None = None,
        files: Mapping[str, str] | None = None,
        response_type: str | None = None,
        _return_http_data_only: bool | None = None,
        collection_formats: dict[str, str] | None = None,
        _request_timeout: float | tuple[float, float] | None = None,
        response_type_map: Mapping[int, str | None] | None = None,
    ) -> DeserializedType | tuple[DeserializedType, int, httpx.Headers] | None:
        """Provide method signature for calling the API."""


class _Unset:
    @staticmethod
    def __bool__() -> Literal[False]:
        return False

    @staticmethod
    def __repr__() -> Literal["<Unset>"]:
        return "<Unset>"


Unset_Type = _Unset
Unset = _Unset()
"""Magic value to indicate a value has not been set."""
