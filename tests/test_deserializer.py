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

import pytest

from ansys.openapi.common._base import ModelBase
from ansys.openapi.common._deserializer import Deserializer
from ansys.openapi.common._exceptions import ApiException, UndefinedObjectWarning
from ansys.openapi.common._model_registry import ModelRegistry


class DictBackedModel(dict, ModelBase):
    swagger_types = {"label": "str"}
    attribute_map = {"label": "Label"}

    def __init__(self, label=None):
        super().__init__()
        self._label = label

    @property
    def label(self):
        return self._label

    @label.setter
    def label(self, label):
        self._label = label


class EmptyModelReturningRawData(ModelBase):
    swagger_types = {}
    attribute_map = {}

    def __init__(self):
        pass


class EmptyModelWithProbeError(ModelBase):
    swagger_types = {}
    attribute_map = {}

    def __init__(self):
        pass

    def get_real_child_model(self, data):
        if data == {}:
            raise ValueError("probe failed")
        raise NotImplementedError


class ModelWithoutDiscriminator(ModelBase):
    swagger_types = {"name": "str"}
    attribute_map = {"name": "Name"}

    def __init__(self, name=None):
        self._name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, name):
        self._name = name

    def get_real_child_model(self, data):
        raise NotImplementedError


@pytest.fixture
def model_registry():
    from . import models

    registry = ModelRegistry()
    registry.register_module(models)
    registry.register("DictBackedModel", DictBackedModel)
    registry.register("EmptyModelReturningRawData", EmptyModelReturningRawData)
    registry.register("EmptyModelWithProbeError", EmptyModelWithProbeError)
    registry.register("ModelWithoutDiscriminator", ModelWithoutDiscriminator)
    return registry


@pytest.fixture
def deserializer(model_registry):
    return Deserializer(model_registry)


class TestDeserializeBasics:
    def test_none_data_returns_none(self, deserializer):
        assert deserializer.deserialize(None, "str") is None

    def test_undefined_object_returns_dict_and_warns(self, deserializer):
        data = {"foo": "bar", "baz": [1, 2, 3]}
        with pytest.warns(
            UndefinedObjectWarning,
            match="Attempting to deserialize an object with no defined type",
        ):
            output = deserializer.deserialize(data, "object")
        assert output == data


class TestDeserializePrimitives:
    @pytest.mark.parametrize(
        ("value", "type_"), (("foo", str), (int(2), int), (2.0, float), (True, bool))
    )
    def test_primitive_round_trip(self, deserializer, value, type_):
        type_ref = type_.__name__
        result = deserializer.deserialize(value, type_ref)
        assert isinstance(result, type_)
        assert result == value

    def test_bytes_round_trip(self, deserializer):
        source_bytes = b"\x66\x6f\x6f"
        result = deserializer.deserialize(source_bytes, "bytes")
        assert isinstance(result, bytes)
        assert result == source_bytes

    @pytest.mark.parametrize(("target_type", "expected_result"), ((int, int(3)), (str, "3.1")))
    def test_float_casts(self, deserializer, target_type, expected_result):
        result = deserializer.deserialize(3.1, target_type.__name__)
        assert isinstance(result, target_type)
        assert result == expected_result

    @pytest.mark.parametrize(
        ("data", "target_type"),
        (
            (5.0, bytes),
            ("foo", int),
            ("foo", float),
            ("foo", bytes),
            (b"\x01", int),
            (b"\x01", float),
        ),
    )
    def test_invalid_primitive_cast_returns_original_data(self, deserializer, data, target_type):
        result = deserializer.deserialize(data, target_type.__name__)
        assert isinstance(result, type(data))
        assert result == data

    def test_primitive_unicode_encode_error_returns_string(self):
        class RaisingInt:
            def __call__(self, data):
                raise UnicodeEncodeError("utf-8", "x", 0, 1, "bad")

        result = Deserializer._deserialize_primitive("value", RaisingInt())
        assert result == "value"


class TestDeserializeCollections:
    def test_list_round_trip(self, deserializer):
        source_list = ["Look", "another", "list"]
        result = deserializer.deserialize(source_list, "list[str]")
        assert isinstance(result, list)
        assert result == source_list

    def test_dict_round_trip(self, deserializer):
        source_dict = {1: "one", 2: "two", 3: "three"}
        result = deserializer.deserialize(source_dict, "dict(int, str)")
        assert isinstance(result, dict)
        assert result == source_dict

    def test_dict_casts_values(self, deserializer):
        source_dict = {"one": 1.0, "two": 2.0, "three": 3.1}
        result = deserializer.deserialize(source_dict, "dict(str, int)")
        assert isinstance(result, dict)
        for key, val in source_dict.items():
            assert key in result
            assert result[key] == int(val)

    @pytest.mark.parametrize(
        ("type_name", "value"),
        [
            ("list[str]", ("foo")),
            ("list[str]", "foo"),
            ("list[str]", 1),
            ("list[str]", 1.0),
            ("list[str]", b"foo"),
            ("list[str]", True),
            ("list[str]", datetime.date.today()),
            ("dict(str, int)", ["foo"]),
            ("dict(str, int)", ("foo")),
            ("dict(str, int)", 1),
            ("dict(str, int)", 1.0),
            ("dict(str, int)", b"foo"),
            ("dict(str, int)", True),
            ("dict(str, int)", datetime.date.today()),
            ("str", ["foo"]),
            ("str", ("foo",)),
            ("str", datetime.date.today()),
            ("int", [1]),
            ("int", (1,)),
            ("int", datetime.date.today()),
            ("float", [1.0]),
            ("float", (1.0,)),
            ("float", datetime.date.today()),
            ("bool", [True]),
            ("bool", (True,)),
            ("bool", datetime.date.today()),
            ("bytes", [b"foo"]),
            ("bytes", (b"foo",)),
            ("bytes", datetime.date.today()),
            ("datetime", ["2023-01-01T00:00:00Z"]),
            ("datetime", ("2023-01-01T00:00:00Z",)),
            ("datetime", datetime.datetime.now()),
            ("datetime", 1),
            ("datetime", 1.0),
            ("datetime", True),
            ("datetime", b"2023-01-01T00:00:00Z"),
            ("date", ["2023-01-01"]),
            ("date", ("2023-01-01",)),
            ("date", datetime.date.today()),
            ("date", 1),
            ("date", 1.0),
            ("date", True),
            ("date", b"2023-01-01"),
        ],
    )
    def test_wrong_type_raises_type_error(self, deserializer, type_name, value):
        with pytest.raises(TypeError) as error:
            deserializer.deserialize(value, type_name)
        assert type_name in str(error.value)
        assert str(type(value)) in str(error.value)


class TestDeserializeDates:
    def test_date_round_trip(self, deserializer):
        source_date = datetime.date(2371, 4, 26)
        result = deserializer.deserialize(source_date.isoformat(), "date")
        assert isinstance(result, datetime.date)
        assert result == source_date

    def test_datetime_round_trip(self, deserializer):
        source_datetime = datetime.datetime(2371, 4, 26, 4, 39, 21)
        result = deserializer.deserialize(source_datetime.isoformat(), "datetime")
        assert isinstance(result, datetime.datetime)
        assert result == source_datetime

    @pytest.mark.parametrize("object_type", ("date", "datetime"))
    def test_invalid_date_like_raises_api_exception(self, deserializer, object_type):
        invalid_date = "NOT-A-DATE"
        with pytest.raises(ApiException) as exception_info:
            deserializer.deserialize(invalid_date, object_type)
        assert invalid_date in exception_info.value.reason_phrase
        assert f"{object_type} object" in exception_info.value.reason_phrase


class TestDeserializeModels:
    def test_model_round_trip(self, deserializer):
        from . import models

        model_instance = models.ExampleModel("foo", 3, False, ["It's", "a", "list"])
        model_dict = {
            "Boolean": False,
            "Integer": 3,
            "ListOfStrings": ["It's", "a", "list"],
            "String": "foo",
        }
        result = deserializer.deserialize(model_dict, "ExampleModel")
        assert isinstance(result, models.ExampleModel)
        assert result == model_instance

    def test_model_from_string_creates_empty_instance(self, deserializer):
        from . import models

        result = deserializer.deserialize("unused", "ExampleModel")
        assert isinstance(result, models.ExampleModel)

    @pytest.mark.parametrize(
        "value", [[("Boolean", False)], (("Boolean", False),), 1, 1.0, True, b"foo"]
    )
    def test_model_with_incorrect_value_type_raises_type_error(self, deserializer, value):
        with pytest.raises(TypeError) as exception_info:
            deserializer.deserialize(value, "ExampleModel")
        assert "dict or string" in str(exception_info.value)

    def test_model_with_discriminator(self, deserializer):
        from . import models

        model_instance = models.ExampleModel("foo", 3, False, ["It's", "a", "list"])
        model_dict = {
            "Boolean": False,
            "Integer": 3,
            "ListOfStrings": ["It's", "a", "list"],
            "String": "foo",
            "modelType": "ExampleModel",
        }
        result = deserializer.deserialize(model_dict, "ExampleBaseModel")
        assert isinstance(result, models.ExampleModel)
        assert result == model_instance

    def test_empty_model_returns_raw_string_data(self, deserializer):
        result = deserializer.deserialize("Good", "EmptyModelReturningRawData")
        assert result == "Good"

    def test_empty_model_continues_after_probe_error(self, deserializer):
        result = deserializer.deserialize("payload", "EmptyModelWithProbeError")
        assert isinstance(result, EmptyModelWithProbeError)

    def test_dict_backed_model_preserves_extra_keys(self, deserializer):
        result = deserializer.deserialize(
            {"Label": "primary", "Extra": 99},
            "DictBackedModel",
        )
        assert isinstance(result, DictBackedModel)
        assert result.label == "primary"
        assert result["Extra"] == 99

    def test_model_without_discriminator_skips_not_implemented(self, deserializer):
        result = deserializer.deserialize({"Name": "widget"}, "ModelWithoutDiscriminator")
        assert isinstance(result, ModelWithoutDiscriminator)
        assert result.name == "widget"


class TestDeserializeEnums:
    def test_enum_model_returns_constant_value(self, deserializer):
        from . import models

        result = deserializer.deserialize("Good", "ExampleModelWithEnum")
        assert result == models.ExampleModelWithEnum().GOOD

    def test_string_enum(self, deserializer):
        from . import models

        result = deserializer.deserialize("Good", "ExampleEnum")
        assert isinstance(result, models.ExampleEnum)
        assert result == models.ExampleEnum.GOOD

    def test_int_enum(self, deserializer):
        from . import models

        result = deserializer.deserialize(200, "ExampleIntEnum")
        assert isinstance(result, models.ExampleIntEnum)
        assert result == models.ExampleIntEnum._200

    @pytest.mark.parametrize(
        ["value", "target_enum", "expected_error_msg"],
        [
            ("200", "ExampleIntEnum", "'200' is not a valid ExampleIntEnum"),
            (4.5, "ExampleIntEnum", "4.5 is not a valid ExampleIntEnum"),
            (4, "ExampleIntEnum", "4 is not a valid ExampleIntEnum"),
            ("SomeValue", "ExampleEnum", "'SomeValue' is not a valid ExampleEnum"),
            (4.5, "ExampleEnum", "4.5 is not a valid ExampleEnum"),
            (4, "ExampleEnum", "4 is not a valid ExampleEnum"),
        ],
    )
    def test_invalid_enum_value_raises_helpful_message(
        self, deserializer, value, target_enum, expected_error_msg
    ):
        with pytest.raises(ValueError, match=expected_error_msg):
            deserializer.deserialize(value, target_enum)
