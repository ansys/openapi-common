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

from enum import Enum
from types import ModuleType
from typing import Dict, Type, Union

from ._base import ModelBase


class ModelRegistry:
    """Maps OpenAPI model and enum type names to their Python classes."""

    def __init__(self) -> None:
        self._models: Dict[str, Union[Type[ModelBase], Type[Enum]]] = {}

    @property
    def models(self) -> Dict[str, Union[Type[ModelBase], Type[Enum]]]:
        """Registered model and enum classes keyed by their OpenAPI type name."""
        return self._models

    def register(self, name: str, klass: Union[Type[ModelBase], Type[Enum]]) -> None:
        """Register a single model or enum class."""
        self._models[name] = klass

    def register_module(self, models: ModuleType) -> None:
        """Register all :class:`ModelBase` and :class:`Enum` classes from a generated models module."""
        for name, value in models.__dict__.items():
            if isinstance(value, type) and (
                issubclass(value, ModelBase) or issubclass(value, Enum)
            ):
                self._models[name] = value

    def get(self, name: str) -> Union[Type[ModelBase], Type[Enum]]:
        """Return the class registered under ``name``."""
        return self._models[name]

    def __contains__(self, name: str) -> bool:
        """Return whether ``name`` is registered."""
        return name in self._models
