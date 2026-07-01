# Copyright (C) 2022 - 2026 Synopsys, Inc. and ANSYS, Inc. All rights reserved.
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
from typing import Callable, Dict, Type, Union
import warnings

from dateutil.parser import parse

from ._base import DeserializedType, ModelBase, PrimitiveType, SerializedType
from ._codec_types import (
    DICT_MATCH_REGEX,
    LIST_MATCH_REGEX,
    NATIVE_TYPES_MAPPING,
    PRIMITIVE_TYPES,
)
from ._exceptions import ApiException, UndefinedObjectWarning
from ._model_registry import ModelRegistry


class Deserializer:
    """Deserializes wire-ready data structures into Python objects."""

    def __init__(self, model_registry: ModelRegistry) -> None:
        self._model_registry = model_registry

    def deserialize(self, data: SerializedType, response_type: str) -> DeserializedType:
        """Deserialize wire-ready data into an object."""
        if data is None:
            return None

        if response_type == "object":
            warnings.warn(
                "Attempting to deserialize an object with no defined type. Returning "
                "the raw data as a dictionary. Check your OpenAPI definition and ensure "
                "all types are fully defined.",
                UndefinedObjectWarning,
            )
            return data

        list_match = LIST_MATCH_REGEX.match(response_type)
        if list_match is not None:
            if not isinstance(data, list):
                raise TypeError(
                    f"Expected list for deserializing to {response_type}, got {type(data)}"
                )
            sub_kls = list_match.group(1)
            return [self.deserialize(sub_data, sub_kls) for sub_data in data]

        dict_match = DICT_MATCH_REGEX.match(response_type)
        if dict_match is not None:
            if not isinstance(data, dict):
                raise TypeError(
                    f"Expected dict for deserializing to {response_type}, got {type(data)}"
                )
            sub_kls = dict_match.group(2)
            return {k: self.deserialize(v, sub_kls) for k, v in data.items()}

        if response_type in NATIVE_TYPES_MAPPING:
            klass = NATIVE_TYPES_MAPPING[response_type]
            if klass in PRIMITIVE_TYPES:
                if not isinstance(data, (str, int, float, bool, bytes)):
                    raise TypeError(
                        f"Expected primitive type for deserializing to {response_type}, got {type(data)}"
                    )
                return self._deserialize_primitive(data, klass)
            elif klass == datetime.date:
                if not isinstance(data, str):
                    raise TypeError(
                        f"Expected string for deserializing to {response_type}, got {type(data)}"
                    )
                return self._deserialize_date(data)
            elif klass == datetime.datetime:
                if not isinstance(data, str):
                    raise TypeError(
                        f"Expected string for deserializing to {response_type}, got {type(data)}"
                    )
                return self._deserialize_datetime(data)

        klass = self._model_registry.get(response_type)
        if issubclass(klass, Enum):
            return klass(data)
        else:
            if not isinstance(data, (dict, str)):
                raise TypeError(
                    f"Expected dict or string for deserializing to {response_type}, got {type(data)}"
                )
            return self._deserialize_model(data, klass)

    @staticmethod
    def _deserialize_primitive(
        data: PrimitiveType, klass: Callable[..., PrimitiveType]
    ) -> PrimitiveType:
        """Deserialize to the primitive type."""
        try:
            return klass(data)
        except UnicodeEncodeError:
            return str(data)
        except (ValueError, TypeError):
            return data

    @staticmethod
    def _deserialize_date(value: str) -> datetime.date:
        """Deserialize string to ``datetime.date``."""
        try:
            return parse(value).date()
        except ValueError:
            raise ApiException(
                status_code=0,
                reason_phrase=f"Failed to parse `{value}` as date object",
            )

    @staticmethod
    def _deserialize_datetime(value: str) -> datetime.datetime:
        """Deserialize string to ``datetime.datetime``."""
        try:
            return parse(value)
        except ValueError:
            raise ApiException(
                status_code=0,
                reason_phrase=f"Failed to parse `{value}` as datetime object",
            )

    def _deserialize_model(
        self, data: Union[Dict, str], klass: Type[ModelBase]
    ) -> Union[ModelBase, Dict, str]:
        """Deserialize model representation to model."""
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
                    kwargs[attr] = self.deserialize(value, attr_type)

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
                instance = self.deserialize(data, klass_name)  # type: ignore[assignment]
        except NotImplementedError:
            pass

        return instance
