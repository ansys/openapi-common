# Copyright (C) 2022 - 2025 ANSYS, Inc. and/or its affiliates.
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

import pytest

from . import models


class TestToDict:
    @pytest.mark.parametrize(
        ["model_instance", "expected_dict"],
        [
            (
                models.ExampleModel("foo", 3, False, ["It's", "a", "list"]),
                {
                    "string_property": "foo",
                    "int_property": 3,
                    "bool_property": False,
                    "list_property": ["It's", "a", "list"],
                },
            ),
            (models.ExampleBaseModel("foo"), {"model_type": "foo"}),
        ],
    )
    def test_model_to_dict(self, model_instance, expected_dict):
        assert model_instance.to_dict() == expected_dict


expected_str_model = """{'bool_property': False,
 'int_property': 3,
 'list_property': ["It's", 'a', 'list'],
 'string_property': 'foo'}"""


class TestToStr:
    @pytest.mark.parametrize(
        ["model_instance", "expected_result"],
        [
            (
                models.ExampleModel("foo", 3, False, ["It's", "a", "list"]),
                expected_str_model,
            ),
            (models.ExampleBaseModel("foo"), "{'model_type': 'foo'}"),
        ],
    )
    def test_model_to_str(self, model_instance, expected_result):
        assert model_instance.to_str() == expected_result
