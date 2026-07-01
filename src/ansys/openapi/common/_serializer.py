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
from typing import Any

from ._base import Unset
from ._codec_types import PRIMITIVE_TYPES


class Serializer:
    """Serializes Python objects into wire-ready structures for OpenAPI clients."""

    def serialize(self, obj: Any) -> Any:
        """Build a JSON-serializable representation of ``obj`` for transmission to the API."""
        if obj is None:
            return None
        elif isinstance(obj, PRIMITIVE_TYPES):
            return obj
        elif isinstance(obj, list):
            return [self.serialize(sub_obj) for sub_obj in obj]
        elif isinstance(obj, tuple):
            return tuple(self.serialize(sub_obj) for sub_obj in obj)
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

        return {key: self.serialize(val) for key, val in obj_dict.items()}
