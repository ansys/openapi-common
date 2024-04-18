# Copyright (C) 2022 - 2024 ANSYS, Inc. and/or its affiliates.
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

from ansys.openapi.common._util import CaseInsensitiveOrderedDict


class TestCaseInsensitiveOrderedDict:
    @pytest.fixture(autouse=True)
    def _example_dict_fixture(self):
        self.example_dict = CaseInsensitiveOrderedDict({"foo": "bar", "BaZ": "qux"})

    def test_get_item(self):
        assert self.example_dict["foo"] == "bar"
        assert self.example_dict["FoO"] == "bar"
        assert self.example_dict["baz"] == "qux"

    def test_set_item(self):
        self.example_dict["FoO"] = "zog"
        assert self.example_dict["foo"] == "zog"

    def test_delete_item(self):
        del self.example_dict["foo"]
        with pytest.raises(KeyError):
            _ = self.example_dict["foo"]
        del self.example_dict["baz"]
        with pytest.raises(KeyError):
            _ = self.example_dict["baz"]

    def test_item_get_method(self):
        assert self.example_dict.get("foo") == "bar"
        assert self.example_dict.get("FoO") == "bar"
        assert self.example_dict.get("baz") == "qux"
        assert self.example_dict.get("grault", None) is None

    def test_setdefault(self):
        assert self.example_dict.setdefault("foo") == "bar"
        assert self.example_dict.setdefault("FoO") == "bar"
        assert self.example_dict.setdefault("gRAuLt", "zog") == "zog"
        assert self.example_dict.setdefault("grault", "ftagn") == "zog"
        assert self.example_dict["grault"] == "zog"

    def test_pop(self):
        assert self.example_dict.pop("foo") == "bar"
        with pytest.raises(KeyError):
            _ = self.example_dict["foo"]
        assert self.example_dict.pop("baz") == "qux"
        with pytest.raises(KeyError):
            _ = self.example_dict["BaZ"]
        assert self.example_dict.pop("grault", "ftagn") == "ftagn"
        default_obj = self.example_dict.pop("spam")
        assert isinstance(default_obj, object)

    def test_update(self):
        self.example_dict.update({"BaZ": "grault", "gRaUlT": "ftagn"})
        assert self.example_dict["baz"] == "grault"
        assert self.example_dict["grault"] == "ftagn"

    def test_contains(self):
        assert "foo" in self.example_dict
        assert "FOo" in self.example_dict
        assert "baz" in self.example_dict
        assert "BaZ" in self.example_dict

    def test_copy(self):
        copied_dict = self.example_dict.copy()
        assert copied_dict == self.example_dict

    def test_from_keys_with_default_value(self):
        new_dict = CaseInsensitiveOrderedDict.fromkeys(("foo", "bar"))
        assert "foo" in new_dict
        assert new_dict["FoO"] is None

    def test_from_keys(self):
        new_dict = CaseInsensitiveOrderedDict.fromkeys(("foo", "bar"), "qux")
        assert "bar" in new_dict
        assert new_dict["BaR"] == "qux"

    def test_repr(self):
        repr = self.example_dict.__repr__()
        dict_from_repr = eval(repr)
        assert dict_from_repr == self.example_dict
