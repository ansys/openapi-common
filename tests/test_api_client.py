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

import datetime
import json
import os
from pathlib import Path
import re
import secrets
import sys
import tempfile
from typing import IO, Dict, Iterable, List, Tuple, Union
import uuid

import pytest
import requests
from requests.packages.urllib3.response import HTTPResponse
import requests_mock
from requests_mock.request import _RequestObjectProxy
from requests_mock.response import _FakeConnection, _IOReader

from ansys.openapi.common import (
    ApiClient,
    ApiException,
    SessionConfiguration,
    UndefinedObjectWarning,
)

from .models import ExampleException

TEST_URL = "http://localhost/api/v1.svc"
UA_STRING = "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0"

VERBS_WITH_BODY = ["DELETE", "PUT", "POST", "PATCH", "OPTIONS"]
VERBS_WITH_FILE_PARAMS = ["PUT", "POST", "PATCH", "OPTIONS"]


@pytest.fixture
def blank_client():
    session = requests.Session()
    client = ApiClient(session, TEST_URL, SessionConfiguration())
    yield client


def test_repr(blank_client):
    assert TEST_URL in str(blank_client)
    assert type(blank_client).__name__ in str(blank_client)


class TestParameterHandling:
    @pytest.fixture(autouse=True)
    def _blank_client(self, blank_client):
        self._client = blank_client

    def test_simple_path_rewrite(self):
        id_ = str(uuid.uuid4())
        single_path = "/resource/{id}"
        result = self._client._ApiClient__handle_path_params(single_path, {"id": id_}, None)
        assert single_path.replace("{id}", id_) == result

    def test_multiple_path_rewrites(self):
        id_ = str(uuid.uuid4())
        name = "TestResource"
        multiple_path = "/resource/{id}/name/{name}"
        result = self._client._ApiClient__handle_path_params(
            multiple_path, {"id": id_, "name": name}, None
        )
        assert multiple_path.replace("{id}", id_).replace("{name}", name) == result

    def test_path_with_naughty_characters(self):
        name = '"Na,ughty!P,ath.'
        naughty_path = "/resource/{name}"
        result = self._client._ApiClient__handle_path_params(naughty_path, {"name": name}, None)
        assert "/resource/%22Na%2Cughty%21P%2Cath." == result

    def test_path_with_naughty_characters_allowed(self):
        name = "<SpecialName>"
        naughty_path = "/resource/{name}"
        self._client.configuration.safe_chars_for_path_param = "<>"
        result = self._client._ApiClient__handle_path_params(naughty_path, {"name": name}, None)
        assert "/resource/<SpecialName>" == result

    def test_single_query(self):
        query = {"name": "Spamalot"}
        result = self._client._ApiClient__handle_query_params(query, None)
        assert "name=Spamalot" == result

    def test_single_query_with_int(self):
        query = {"count": 0}
        result = self._client._ApiClient__handle_query_params(query, None)
        assert "count=0" == result

    def test_multiple_queries(self):
        query = {"bird": "swallow", "type": "african"}
        result = self._client._ApiClient__handle_query_params(query, None)
        assert "bird=swallow&type=african" == result

    def test_multiple_queries_with_ints(self):
        query = {"start": 0, "finish": 10}
        result = self._client._ApiClient__handle_query_params(query, None)
        assert "start=0&finish=10" == result

    def test_simple_query_with_collection(self):
        query = {"bird": "swallow", "type": ("african", "european")}
        result = self._client._ApiClient__handle_query_params(query, {"type": "pipes"})
        assert "bird=swallow&type=african|european" == result

    def test_query_with_naughty_characters(self):
        query = {"search": '"A &Naughty#Qu,ery@100%'}
        result = self._client._ApiClient__handle_query_params(query, None)
        assert 'search="A &Naughty#Qu,ery@100%' == result


class TestSerialization:
    _test_value_list = ["foo", int(2), 2.0, True]
    _test_value_types = [str, int, float, bool]

    @pytest.fixture(autouse=True)
    def _blank_client(self, blank_client):
        self._client = blank_client

    def test_serialize_none(self):
        assert self._client.sanitize_for_serialization(None) is None

    @pytest.mark.parametrize(
        ("value", "type_"),
        (
            ("foo", str),
            (b"\x66\x6f\x6f", bytes),
            (int(2), int),
            (2.0, float),
            (True, bool),
        ),
    )
    def test_serialize_primitive(self, value, type_):
        serialized_primitive = self._client.sanitize_for_serialization(value)
        assert isinstance(serialized_primitive, type_)
        assert serialized_primitive == value

    def test_serialize_list(self):
        serialized_list = self._client.sanitize_for_serialization(self._test_value_list)
        assert isinstance(serialized_list, list)
        assert len(serialized_list) == len(self._test_value_list)
        for value, source_value, type_ in zip(
            serialized_list, self._test_value_list, self._test_value_types
        ):
            assert isinstance(value, type_)
            assert value == source_value

    def test_serialize_tuple(self):
        source_tuple = tuple(self._test_value_list)
        serialized_tuple = self._client.sanitize_for_serialization(source_tuple)
        assert isinstance(serialized_tuple, tuple)
        assert len(serialized_tuple) == len(source_tuple)
        for value, source_value, type_ in zip(
            serialized_tuple, source_tuple, self._test_value_types
        ):
            assert isinstance(value, type_)
            assert value == source_value

    def test_serialize_dict(self):
        source_dict = {k.__name__: v for k, v in zip(self._test_value_types, self._test_value_list)}
        serialized_dict = self._client.sanitize_for_serialization(source_dict)
        assert isinstance(serialized_dict, dict)
        assert len(serialized_dict.keys()) == len(self._test_value_list)
        for type_ in self._test_value_types:
            type_name = type_.__name__
            assert type_name in serialized_dict.keys()
            assert isinstance(serialized_dict[type_name], type_)
            assert serialized_dict[type_name] == source_dict[type_name]

    def test_serialize_date(self):
        source_date = datetime.date(2371, 4, 26)
        date_string = source_date.isoformat()
        serialized_date = self._client.sanitize_for_serialization(source_date)
        assert isinstance(serialized_date, str)
        assert serialized_date == date_string

    def test_serialize_datetime(self):
        source_datetime = datetime.datetime(2371, 4, 26, 4, 39, 21)
        datetime_string = source_datetime.isoformat()
        serialized_datetime = self._client.sanitize_for_serialization(source_datetime)
        assert isinstance(serialized_datetime, str)
        assert serialized_datetime == datetime_string

    def test_serialize_model(self):
        from . import models

        self._client.setup_client(models)
        model_instance = models.ExampleModel("foo", 3, False, ["It's", "a", "list"])
        model_dict = {
            "Boolean": False,
            "Integer": 3,
            "ListOfStrings": ["It's", "a", "list"],
            "String": "foo",
        }
        serialized_model = self._client.sanitize_for_serialization(model_instance)
        assert serialized_model == model_dict

    def test_serialize_model_null_values(self):
        from . import models

        self._client.setup_client(models)
        model_instance = models.ExampleModel("foo", None, False, None)
        model_dict = {
            "Boolean": False,
            "Integer": None,
            "ListOfStrings": None,
            "String": "foo",
        }
        serialized_model = self._client.sanitize_for_serialization(model_instance)
        assert serialized_model == model_dict

    def test_serialize_model_unset_values(self):
        from . import models

        self._client.setup_client(models)
        model_instance = models.ExampleModel(int_property=3, list_property=["It's", "a", "list"])
        model_dict = {
            "Integer": 3,
            "ListOfStrings": ["It's", "a", "list"],
        }
        serialized_model = self._client.sanitize_for_serialization(model_instance)
        assert serialized_model == model_dict

    def test_serialize_model_set_unset_and_null_values(self):
        from . import models

        self._client.setup_client(models)
        model_instance = models.ExampleModel(int_property=None, list_property=["It's", "a", "list"])
        model_dict = {
            "Integer": None,
            "ListOfStrings": ["It's", "a", "list"],
        }
        serialized_model = self._client.sanitize_for_serialization(model_instance)
        assert serialized_model == model_dict

    def test_serialize_enum_model(self):
        from . import models

        self._client.setup_client(models)
        model_instance = models.ExampleModelWithEnum().GOOD
        model_value = "Good"
        serialized_model = self._client.sanitize_for_serialization(model_instance)
        assert serialized_model == model_value

    def test_serialize_enum(self):
        from . import models

        self._client.setup_client(models)
        enum_instance = models.ExampleEnum.GOOD
        serialized_enum = self._client.sanitize_for_serialization(enum_instance)
        assert serialized_enum == "Good"


class TestDeserialization:
    _test_value_list = ["foo", int(2), 2.0, True]
    _test_value_types = [str, int, float, bool]

    @pytest.fixture(autouse=True)
    def _blank_client(self, blank_client):
        self._client = blank_client

    def test_deserialize_none(self):
        assert self._client._ApiClient__deserialize(None, "") is None

    @pytest.mark.parametrize(
        ("value", "type_"), (("foo", str), (int(2), int), (2.0, float), (True, bool))
    )
    def test_deserialize_primitive(self, value, type_):
        type_ref = type_.__name__
        deserialized_primitive = self._client._ApiClient__deserialize(value, type_ref)
        assert isinstance(deserialized_primitive, type_)
        assert deserialized_primitive == value

    @pytest.mark.parametrize(("target_type", "expected_result"), ((int, int(3)), (str, "3.1")))
    def test_deserialize_float_casts(self, target_type, expected_result):
        test_float = 3.1
        deserialized_object = self._client._ApiClient__deserialize(test_float, target_type.__name__)
        assert isinstance(deserialized_object, target_type)
        assert deserialized_object == expected_result

    def test_deserialize_bytes(self):
        source_bytes = b"\x66\x6f\x6f"
        deserialized_bytes = self._client._ApiClient__deserialize(source_bytes, "bytes")
        assert isinstance(deserialized_bytes, bytes)
        assert deserialized_bytes == source_bytes

    def test_deserialize_list(self):
        source_list = ["Look", "another", "list"]
        deserialized_list = self._client._ApiClient__deserialize(source_list, "list[str]")
        assert isinstance(deserialized_list, list)
        assert deserialized_list == source_list

    def test_deserialize_dict(self):
        source_dict = {1: "one", 2: "two", 3: "three"}
        deserialized_dict = self._client._ApiClient__deserialize(source_dict, "dict(int, str)")
        assert isinstance(deserialized_dict, dict)
        assert deserialized_dict == source_dict

    def test_deserialize_dict_casts_ints(self):
        source_dict = {"one": 1.0, "two": 2.0, "three": 3.1}
        deserialized_dict = self._client._ApiClient__deserialize(source_dict, "dict(str, int)")
        assert isinstance(deserialized_dict, dict)
        for key, val in source_dict.items():
            assert key in deserialized_dict
            assert deserialized_dict[key] == int(val)

    def test_deserialize_date(self):
        source_date = datetime.date(2371, 4, 26)
        date_string = source_date.isoformat()
        type_ref = "date"
        deserialized_date = self._client._ApiClient__deserialize(date_string, type_ref)
        assert isinstance(deserialized_date, datetime.date)
        assert deserialized_date == source_date

    @pytest.mark.parametrize("object_type", ("date", "datetime"))
    def test_invalid_date_like_throws(self, object_type):
        invalid_date = "NOT-A-DATE"
        with pytest.raises(ApiException) as exception_info:
            _ = self._client._ApiClient__deserialize(invalid_date, object_type)
        assert invalid_date in exception_info.value.reason_phrase
        assert f"{object_type} object" in exception_info.value.reason_phrase

    def test_deserialize_datetime(self):
        source_datetime = datetime.datetime(2371, 4, 26, 4, 39, 21)
        datetime_string = source_datetime.isoformat()
        type_ref = "datetime"
        deserialized_datetime = self._client._ApiClient__deserialize(datetime_string, type_ref)
        assert isinstance(deserialized_datetime, datetime.datetime)
        assert deserialized_datetime == source_datetime

    def test_deserialize_model(self):
        from . import models

        self._client.setup_client(models)

        model_instance = models.ExampleModel("foo", 3, False, ["It's", "a", "list"])
        model_dict = {
            "Boolean": False,
            "Integer": 3,
            "ListOfStrings": ["It's", "a", "list"],
            "String": "foo",
        }
        type_ref = "ExampleModel"
        deserialized_model = self._client._ApiClient__deserialize(model_dict, type_ref)
        assert isinstance(deserialized_model, models.ExampleModel)
        assert deserialized_model == model_instance

    @pytest.mark.parametrize(
        "value", [[("Boolean", False)], (("Boolean", False),), 1, 1.0, True, b"foo"]
    )
    def test_deserialize_model_with_incorrect_value_type_raises_type_error(self, value):
        from . import models

        self._client.setup_client(models)

        type_ref = "ExampleModel"
        with pytest.raises(TypeError) as exception_info:
            _ = self._client._ApiClient__deserialize(value, type_ref)
        assert "dict or string" in str(exception_info.value)

    def test_deserialize_model_with_discriminator(self):
        from . import models

        self._client.setup_client(models)

        model_instance = models.ExampleModel("foo", 3, False, ["It's", "a", "list"])
        model_dict = {
            "Boolean": False,
            "Integer": 3,
            "ListOfStrings": ["It's", "a", "list"],
            "String": "foo",
            "modelType": "ExampleModel",
        }
        type_ref = "ExampleBaseModel"
        deserialized_model = self._client._ApiClient__deserialize(model_dict, type_ref)
        assert isinstance(deserialized_model, models.ExampleModel)
        assert deserialized_model == model_instance

    def test_deserialize_enum_model(self):
        from . import models

        self._client.setup_client(models)
        model_instance = models.ExampleModelWithEnum().GOOD
        model_value = "Good"
        type_ref = "ExampleModelWithEnum"
        serialized_model = self._client._ApiClient__deserialize(model_value, type_ref)
        assert serialized_model == model_instance

    def test_deserialize_enum(self):
        from . import models

        self._client.setup_client(models)
        value = "Good"
        type_ref = "ExampleEnum"
        serialized_enum = self._client._ApiClient__deserialize(value, type_ref)
        assert isinstance(serialized_enum, models.ExampleEnum)
        assert serialized_enum == models.ExampleEnum.GOOD

    def test_deserialize_int_enum(self):
        from . import models

        self._client.setup_client(models)
        value = 200
        type_ref = "ExampleIntEnum"
        serialized_enum = self._client._ApiClient__deserialize(value, type_ref)
        assert isinstance(serialized_enum, models.ExampleIntEnum)
        assert serialized_enum == models.ExampleIntEnum._200

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
    def test_deserialize_enums_raises_helpful_message_on_wrong_value(
        self, value, target_enum, expected_error_msg
    ):
        from . import models

        self._client.setup_client(models)
        with pytest.raises(ValueError, match=expected_error_msg):
            _ = self._client._ApiClient__deserialize(value, target_enum)

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
    def test_deserialize_primitive_of_wrong_type_does_nothing(self, data, target_type):
        output = self._client._ApiClient__deserialize_primitive(data, target_type)
        assert isinstance(output, type(data))
        assert output == data

    def test_deserialize_undefined_object_returns_dict_and_warns(self):
        data = {"foo": "bar", "baz": [1, 2, 3]}
        with pytest.warns(
            UndefinedObjectWarning,
            match="Attempting to deserialize an object with no defined type",
        ):
            output = self._client._ApiClient__deserialize(data, "object")
        assert output == data

    @pytest.mark.parametrize(
        ("type_name, value"),
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
    def test_deserialize_wrong_type_raises_type_error_simple(self, type_name, value):
        with pytest.raises(TypeError) as e:
            _ = self._client._ApiClient__deserialize(value, type_name)
        assert type_name in str(e.value)
        assert str(type(value)) in str(e.value)


class TestResponseParsing:
    from requests.adapters import HTTPAdapter

    _http_adapter = HTTPAdapter()
    _connection = _FakeConnection()
    """Test handling of requests.Response objects based on response_type"""

    @pytest.fixture(autouse=True)
    def _blank_client(self, blank_client):
        self._client = blank_client

    def create_response(
        self,
        json_: Dict = None,
        text: str = None,
        content: bytes = None,
        headers=None,
        content_type="application/json",
    ):
        body = _IOReader()
        if json_ is not None:
            text = json.dumps(json_)
        if text is not None:
            content = text.encode("utf-8")
        if content is not None:
            body = _IOReader(content)
        status = 200
        reason = "OK"
        if headers is None:
            headers = {}
        headers["Content-Type"] = content_type

        raw = HTTPResponse(
            status=status,
            reason=reason,
            headers=headers,
            body=body or _IOReader(b""),
            decode_content=False,
            preload_content=False,
            original_response=None,
        )

        request = requests.Request()
        response = self._http_adapter.build_response(request, raw)
        response.connection = self._connection
        return response

    def test_response_is_not_deserialized_if_type_is_none(self, mocker):
        data = {"one": 1, "two": 2, "three": 3}
        response = self.create_response(data)
        _deserialize_mock = mocker.patch.object(ApiClient, "_ApiClient__deserialize")
        result = self._client.deserialize(response, None)
        assert result is None
        _deserialize_mock.assert_not_called()

    def test_json_parsed_as_json(self, mocker):
        data = {"one": 1, "two": 2, "three": 3}
        response = self.create_response(data)
        deserialize_mock = mocker.patch.object(ApiClient, "_ApiClient__deserialize")
        deserialize_mock.return_value = True
        _ = self._client.deserialize(response, "dict")
        deserialize_mock.assert_called()
        deserialize_mock.assert_called_once_with(data, "dict")

    def test_text_parsed_as_text(self, mocker):
        data = "This is some data this is definitely not json, it should be rendered as a string"
        response = self.create_response(text=data, content_type="text/plain")
        deserialize_mock = mocker.patch.object(ApiClient, "_ApiClient__deserialize")
        deserialize_mock.return_value = True
        _ = self._client.deserialize(response, "str")
        deserialize_mock.assert_called()
        deserialize_mock.assert_called_once_with(data, "str")

    def test_deserialize_json_as_string_returns_string(self, mocker):
        data = json.dumps({"foo": "bar", "baz": [1, 2, 3]})
        response = self.create_response(text=data, content_type="text/plain")
        deserialize_mock = mocker.patch.object(ApiClient, "_ApiClient__deserialize")
        deserialize_mock.return_value = True
        _ = self._client.deserialize(response, "str")
        deserialize_mock.assert_called()
        deserialize_mock.assert_called_once_with(data, "str")

    @pytest.mark.parametrize("provide_content_type", (True, False))
    def test_application_data_is_not_parsed(self, mocker, provide_content_type):
        # The false case tests the default handling of non-json data
        data = b"This is some data this is definitely not json, it should be rendered as application/octet-stream"
        response = self.create_response(content=data, content_type="application/octet-stream")
        if not provide_content_type:
            response.headers.pop("Content-Type")
        deserialize_mock = mocker.patch.object(ApiClient, "_ApiClient__deserialize")
        deserialize_mock.return_value = True
        _ = self._client.deserialize(response, "bytes")
        deserialize_mock.assert_called()
        deserialize_mock.assert_called_once_with(data, "bytes")

    def test_xml_is_returned_as_text(self, mocker):
        data = """<note>
            <to>Tove</to>
            <from>Jani</from>
            <heading>Reminder</heading>
            <body>Don't forget me this weekend!</body>
        </note>"""
        response = self.create_response(text=data, content_type="application/xml")
        deserialize_mock = mocker.patch.object(ApiClient, "_ApiClient__deserialize")
        deserialize_mock.return_value = True
        _ = self._client.deserialize(response, "str")
        deserialize_mock.assert_called()
        deserialize_mock.assert_called_once_with(data, "str")

    def test_file_with_no_name_is_saved(self):
        data = b"Here is some file data to save"
        response = self.create_response(content=data, content_type="application/octet-stream")
        file_path = self._client.deserialize(response, "file")
        assert os.path.exists(file_path)
        with open(file_path, "rb") as output_file:
            saved_data = output_file.read()
        os.remove(file_path)
        assert saved_data == data

    def test_file_with_name_is_saved(self):
        data = b"Here is some file data to save"
        file_name = "test.xml"

        response = self.create_response(
            content=data,
            headers={"Content-Disposition": f'filename="{file_name}"'},
            content_type="application/octet-stream",
        )
        file_path = self._client.deserialize(response, "file")

        assert os.path.exists(file_path)

        saved_name = os.path.basename(file_path)
        assert saved_name == file_name

        with open(file_path, "rb") as output_file:
            saved_data = output_file.read()
        os.remove(file_path)

        assert saved_data == data

    def test_file_with_header_no_name_is_saved(self):
        data = b"Here is some file data to save"
        disposition = "very-sad"

        response = self.create_response(
            content=data,
            headers={"Content-Disposition": disposition},
            content_type="application/octet-stream",
        )
        file_path = self._client.deserialize(response, "file")

        assert os.path.exists(file_path)

        saved_name = os.path.basename(file_path)
        assert saved_name != disposition

        with open(file_path, "rb") as output_file:
            saved_data = output_file.read()
        os.remove(file_path)

        assert saved_data == data


class TestRequestDispatch:
    """Test dispatching requests based on parameters and request name"""

    url = "https://my-api.com/api.svc"
    timeout = 22.0
    query_params = "foo=bar&baz=qux"
    post_params = [("clientId", secrets.token_hex(32))]
    header_params = {"Accept": "application/json"}
    stream = False
    body = {
        "str": "foo",
        "int": 12,
        "array": ["foo", "bar"],
        "bool": False,
        "object": {"none": None, "float": 3.1},
    }

    verbs = ("GET", "HEAD", "OPTIONS", "POST", "PATCH", "PUT", "DELETE")
    method_names = ("get", "head", "options", "post", "patch", "put", "delete")

    def send_request(self, verb: str):
        return self._client.request(
            method=verb,
            url=self.url,
            query_params=self.query_params,
            headers=self.header_params,
            post_params=self.post_params,
            body=self.body,
            _preload_content=self.stream,
            _request_timeout=self.timeout,
        )

    def assert_responses(self, verb, request_mock):
        kwarg_assertions = {
            "params": self.query_params,
            "stream": self.stream,
            "timeout": self.timeout,
            "headers": self.header_params,
        }
        if verb in VERBS_WITH_BODY:
            kwarg_assertions["data"] = self.body
        if verb in VERBS_WITH_FILE_PARAMS:
            kwarg_assertions["files"] = self.post_params

        request_mock.assert_called()
        request_mock.assert_called_once_with(self.url, **kwarg_assertions)

    @pytest.fixture(autouse=True)
    def _blank_client(self):
        self._transport = requests.Session()
        self._client = ApiClient(self._transport, TEST_URL, SessionConfiguration())

    @pytest.mark.parametrize(("verb", "method_call"), (zip(verbs, method_names)))
    def test_request_dispatch(self, mocker, verb, method_call):
        # TODO: Can we move the logic deciding which parameters must be provided into the test, rather than the
        #  function above?
        request_mock = mocker.patch.object(requests.Session, method_call)
        request_mock.return_value = True
        _ = self.send_request(verb)
        self.assert_responses(verb, request_mock)

    def test_invalid_verb(self):
        with pytest.raises(ValueError):
            _ = self._client.request("WABBAJACK", self.url)


class TestResponseHandling:
    """Test handling of responses and initial parsing"""

    @pytest.fixture(autouse=True)
    def _blank_client(self):
        from . import models

        self._transport = requests.Session()
        self._client = ApiClient(self._transport, TEST_URL, SessionConfiguration())
        self._client.setup_client(models)
        self._adapter = requests_mock.Adapter()
        self._transport.mount(TEST_URL, self._adapter)

    def test_get_health_info(self):
        """This test represents a simple get request to a health style endpoint, returning 200 OK as a response. It also
        exercises the full response handling, checking the headers and status as well as the text. Other tests will not
        do this."""
        resource_path = "/health"
        method = "GET"

        expected_url = TEST_URL + resource_path

        self._adapter.register_uri(
            "GET",
            expected_url,
            status_code=200,
            content="OK".encode("utf-8"),
            headers={"Content-Type": "text/plain"},
        )
        response, status_code, headers = self._client.call_api(
            resource_path, method, response_type=None
        )

        assert response is None
        assert status_code == 200
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "text/plain"

    def test_post_model(self):
        """This test represents uploading a new record to a server, the server will respond with 201 created and a
        string ID for the new object"""

        expected_request = {
            "String": "new_model",
            "Integer": 1,
            "ListOfStrings": ["red", "green"],
            "Boolean": False,
        }

        def content_json_matcher(request: _RequestObjectProxy):
            json_body = request.text
            json_obj = json.loads(json_body)
            return json_obj == expected_request

        resource_path = "/models"
        method = "POST"
        response_type = "str"

        expected_url = TEST_URL + resource_path

        from tests.models import ExampleModel

        upload_data = ExampleModel(
            string_property="new_model",
            int_property=1,
            list_property=["red", "green"],
            bool_property=False,
        )

        created_id = str(uuid.uuid4())

        with requests_mock.Mocker() as m:
            m.post(
                expected_url,
                additional_matcher=content_json_matcher,
                status_code=201,
                text=created_id,
                headers={"Content-Type": "text/plain"},
            )
            response, status_code, headers = self._client.call_api(
                resource_path, method, body=upload_data, response_type=response_type
            )
        assert response == created_id
        assert status_code == 201
        assert "Content-Type" in headers
        assert headers["Content-Type"] == "text/plain"

    def test_get_model_raises_exception_with_deserialized_response(self):
        """This test represents getting an object from a server which returns a defined exception object when the
        requested id does not exist."""

        resource_path = "/items"
        method = "GET"

        expected_url = TEST_URL + resource_path

        exception_text = "Item not found"
        exception_code = 1
        stack_trace = [
            "Source lines",
            "101: if id_ not in items:",
            "102:     raise ItemNotFound(id_)",
        ]

        response = {
            "ExceptionText": exception_text,
            "ExceptionCode": exception_code,
            "StackTrace": stack_trace,
        }
        response_type_map = {200: "ExampleModel", 404: "ExampleException"}

        self._adapter.register_uri(
            "GET",
            expected_url,
            status_code=404,
            json=response,
            headers={"Content-Type": "application/json"},
        )

        with pytest.raises(ApiException) as e:
            _, _, _ = self._client.call_api(
                resource_path, method, response_type_map=response_type_map
            )

        assert e.value.status_code == 404
        assert "Content-Type" in e.value.headers
        assert e.value.headers["Content-Type"] == "application/json"
        exception_model = e.value.exception_model
        assert exception_model is not None
        assert isinstance(exception_model, ExampleException)
        assert exception_model.exception_text == exception_text
        assert exception_model.exception_code == exception_code
        assert exception_model.stack_trace == stack_trace

    def test_get_model_raises_exception_with_no_deserialized_response(self):
        """This test represents getting an object from a server which returns a defined exception object when the
        requested id does not exist."""

        resource_path = "/items"
        method = "GET"

        expected_url = TEST_URL + resource_path

        exception_text = "Item not found"
        exception_code = 1
        stack_trace = [
            "Source lines",
            "101: if id_ not in items:",
            "102:     raise ItemNotFound(id_)",
        ]

        response = {
            "ExceptionText": exception_text,
            "ExceptionCode": exception_code,
            "StackTrace": stack_trace,
        }
        response_type_map = {200: "ExampleModel", 404: "ExampleException"}

        self._adapter.register_uri(
            "GET",
            expected_url,
            status_code=500,
            json=response,
            headers={"Content-Type": "application/json"},
        )
        with pytest.raises(ApiException) as e:
            _, _, _ = self._client.call_api(
                resource_path, method, response_type_map=response_type_map
            )
        assert e.value.status_code == 500
        assert exception_text in e.value.body
        assert "Content-Type" in e.value.headers
        assert e.value.headers["Content-Type"] == "application/json"

    def test_get_object_with_preload_false_returns_raw_response(self):
        """This test represents getting an object from a server where we do not want to deserialize the response
        immediately"""

        resource_path = "/items/1"
        method = "GET"

        expected_url = TEST_URL + resource_path

        api_response = {
            "String": "new_model",
            "Integer": 1,
            "ListOfStrings": ["red", "yellow", "green"],
            "Boolean": False,
        }
        response_type_map = {200: "ExampleModel"}

        with requests_mock.Mocker() as m:
            m.get(
                expected_url,
                status_code=200,
                json=api_response,
                headers={"Content-Type": "application/json"},
            )
            response = self._client.call_api(
                resource_path,
                method,
                response_type_map=response_type_map,
                _preload_content=False,
                _return_http_data_only=True,
            )

        assert isinstance(response, requests.Response)
        assert response.status_code == 200
        assert response.text == json.dumps(api_response)

    def test_get_object_with_preload_false_raises_exception(self):
        """This test represents getting an object from a server where we do not want to deserialize the response
        immediately, but an exception is returned."""

        resource_path = "/items/1"
        method = "GET"

        expected_url = TEST_URL + resource_path

        exception_text = "Item not found"
        exception_code = 1
        stack_trace = [
            "Source lines",
            "101: if id_ not in items:",
            "102:     raise ItemNotFound(id_)",
        ]

        api_response = {
            "ExceptionText": exception_text,
            "ExceptionCode": exception_code,
            "StackTrace": stack_trace,
        }

        response_type_map = {200: "ExampleModel", 404: "ExampleException"}

        with requests_mock.Mocker() as m:
            m.get(
                expected_url,
                status_code=404,
                json=api_response,
                reason="Not Found",
                headers={"Content-Type": "application/json"},
            )
            with pytest.raises(ApiException) as e:
                _ = self._client.call_api(
                    resource_path,
                    method,
                    response_type_map=response_type_map,
                    _preload_content=False,
                    _return_http_data_only=True,
                )

        assert e.value.status_code == 404
        assert e.value.reason_phrase == "Not Found"
        assert e.value.body == json.dumps(api_response)

    def test_patch_object(self):
        """This test represents updating a value on an existing record using a custom json payload. The new object
        is returned. This questionable API accepts an ID as a query param and returns the updated object
        """

        expected_request = {
            "ListOfStrings": ["red", "yellow", "green"],
        }

        response = {
            "String": "new_model",
            "Integer": 1,
            "ListOfStrings": ["red", "yellow", "green"],
            "Boolean": False,
        }

        from .models import ExampleModel

        deserialized_response = ExampleModel(
            string_property="new_model",
            int_property=1,
            list_property=["red", "yellow", "green"],
            bool_property=False,
        )

        def content_json_matcher(request: _RequestObjectProxy):
            json_body = request.text
            json_obj = json.loads(json_body)
            return json_obj == expected_request

        resource_path = "/models/{ID}"
        method = "PATCH"
        record_id = str(uuid.uuid4())
        path_params = {"ID": record_id}

        response_type = "ExampleModel"

        expected_url = TEST_URL + f"/models/{record_id}"

        upload_data = expected_request

        with requests_mock.Mocker() as m:
            m.patch(
                expected_url,
                additional_matcher=content_json_matcher,
                status_code=200,
                json=response,
                headers={"Content-Type": "application/json"},
            )
            response = self._client.call_api(
                resource_path,
                method,
                path_params=path_params,
                body=upload_data,
                response_type=response_type,
                _return_http_data_only=True,
            )
        assert response == deserialized_response

    def test_delete_object(self):
        """This test represents the deletion of a record by string ID, the server responds with 404 as the object
        does not exist"""

        record_id = str(uuid.uuid4())

        def content_json_matcher(request: _RequestObjectProxy):
            request_body = request.text
            return request_body == record_id

        resource_path = "/models"
        method = "DELETE"

        query_params = {"recordId": record_id}

        expected_url = TEST_URL + resource_path + f"?recordId={record_id}"

        with requests_mock.Mocker() as m:
            m.delete(
                expected_url,
                additional_matcher=content_json_matcher,
                status_code=404,
                reason="Not Found",
                headers={"Content-Type": "text/plain"},
            )
            with pytest.raises(ApiException) as excinfo:
                _ = self._client.call_api(
                    resource_path,
                    method,
                    query_params=query_params,
                    body=record_id,
                    response_type="str",
                    _return_http_data_only=True,
                )

        assert excinfo.value.status_code == 404
        assert excinfo.value.reason_phrase == "Not Found"

    @pytest.fixture
    def file_context(self):
        file_name_list = []
        file_contents_list = []

        def create_files_for_test(file_count: int) -> Tuple[List[str], List[bytes]]:
            for file_index in range(0, file_count):
                fd, path = tempfile.mkstemp()
                os.close(fd)
                file_contents = secrets.token_bytes(256)
                with open(path, "wb") as f:
                    f.write(file_contents)
                file_name_list.append(path)
                file_contents_list.append(file_contents)
            return file_name_list, file_contents_list

        yield create_files_for_test

        for file_name in file_name_list:
            os.remove(file_name)

    def test_file_upload(self, file_context):
        """This test represents an endpoint which accepts a file upload, the server will respond with 413"""

        def content_json_matcher(request: _RequestObjectProxy):
            request_body = request.body
            return b"file_content" and file_content in request_body

        resource_path = "/files"
        method = "POST"

        expected_url = TEST_URL + resource_path

        file_names, file_contents = file_context(1)
        file_name = file_names[0]
        file_content = file_contents[0]

        with requests_mock.Mocker() as m:
            m.post(
                expected_url,
                additional_matcher=content_json_matcher,
                status_code=413,
                reason="Payload Too Large",
                headers={"Content-Type": "text/plain"},
            )
            with pytest.raises(ApiException) as excinfo:
                _ = self._client.call_api(
                    resource_path,
                    method,
                    files={"file_content": file_name},
                    header_params={"Content-Disposition": f'filename="{file_name}"'},
                    response_type="str",
                    _return_http_data_only=True,
                )

        assert excinfo.value.status_code == 413
        assert excinfo.value.reason_phrase == "Payload Too Large"


_RESPONSE_TYPE_MAP = {200: "ExampleModel", 201: "str", 202: None, 404: "ExampleException"}


class TestMultipleResponseTypesHandling:
    """Test deserialization is correctly called based on the different options available to configure response parsing"""

    @pytest.fixture(autouse=True)
    def _blank_client(self):
        from .models import example_model

        self._transport = requests.Session()
        self._client = ApiClient(self._transport, TEST_URL, SessionConfiguration())
        self._client.setup_client(example_model)
        self._adapter = requests_mock.Adapter()
        self._transport.mount(TEST_URL, self._adapter)
        self._model = example_model

    @pytest.mark.parametrize(
        ["response_code", "response_type_map", "response_type", "expected_type"],
        [
            # Check that the correct type is used for deserialization when a response type map is provided
            (200, _RESPONSE_TYPE_MAP, None, "ExampleModel"),
            (201, _RESPONSE_TYPE_MAP, None, "str"),
            (202, _RESPONSE_TYPE_MAP, None, None),
            # Check that response_type is used for deserialization if a response type map is not provided
            (200, None, "ExampleModel", "ExampleModel"),
            (200, None, "str", "str"),
            (200, None, "ExampleException", "ExampleException"),
            # Check that if both the response_type and response_type_map are provided, the map takes precedence
            (200, _RESPONSE_TYPE_MAP, "str", "ExampleModel"),
            (201, _RESPONSE_TYPE_MAP, "ExampleModel", "str"),
            (202, _RESPONSE_TYPE_MAP, "str", None),
            # Even if the map is empty.
            (200, {}, "str", None),
            (200, {}, "ExampleModel", None),
            (200, {}, "ExampleException", None),
            # If neither are provided, check there is no attempt to deserialize
            (200, None, None, None),
        ],
    )
    def test_response_type_handling(
        self,
        mocker,
        response_code: int,
        response_type_map,
        response_type,
        expected_type,
    ):
        resource_path = "/models"
        method = "POST"

        expected_url = TEST_URL + resource_path
        deserialize_mock = mocker.patch.object(ApiClient, "deserialize")
        with requests_mock.Mocker() as m:
            m.post(
                expected_url,
                status_code=response_code,
            )
            _ = self._client.call_api(
                resource_path,
                method,
                response_type=response_type,
                response_type_map=response_type_map,
            )

        deserialize_mock.assert_called_once()
        last_call_pos_args = deserialize_mock.call_args[0]
        assert last_call_pos_args[1] == expected_type

    @pytest.mark.parametrize(
        ["response_code", "response_type_map", "response_type", "expected_type"],
        [
            # Check that the correct type is used for deserialization when a response type map is provided
            (404, _RESPONSE_TYPE_MAP, None, "ExampleException"),
            (400, _RESPONSE_TYPE_MAP, None, None),
            # Check that response_type is used for deserialization if a response type map is not provided
            (404, None, "ExampleException", "ExampleException"),
            (400, None, "ExampleException", "ExampleException"),
            # Check that if both the response_type and response_type_map are provided, the map takes precedence
            (404, _RESPONSE_TYPE_MAP, "str", "ExampleException"),
            (400, _RESPONSE_TYPE_MAP, "str", None),
            # Even if the map is empty.
            (404, {}, "str", None),
            (404, {}, "ExampleException", None),
            # If neither are provided, check there is no attempt to deserialize
            (404, None, None, None),
        ],
    )
    def test_response_type_handling_of_exceptions(
        self,
        mocker,
        response_code: int,
        response_type_map,
        response_type,
        expected_type,
    ):
        resource_path = "/items"
        method = "GET"

        expected_url = TEST_URL + resource_path
        deserialize_mock = mocker.patch.object(ApiClient, "deserialize")
        with requests_mock.Mocker() as m:
            m.get(
                expected_url,
                status_code=response_code,
            )
            with pytest.raises(ApiException) as excinfo:
                _ = self._client.call_api(
                    resource_path,
                    method,
                    response_type=response_type,
                    response_type_map=response_type_map,
                )

        deserialize_mock.assert_called_once()
        last_call_pos_args = deserialize_mock.call_args[0]
        assert last_call_pos_args[1] == expected_type


class TestStaticMethods:
    """Test miscellaneous static methods on the ApiClient class"""

    def test_accepts_none(self):
        assert ApiClient.select_header_accept(None) is None

    def test_accepts_one(self):
        accepts = ["text/xml"]
        expected = "text/xml"
        assert ApiClient.select_header_accept(accepts) == expected

    def test_accepts_multiple(self):
        accepts = ["text/xml", "application/json"]
        expected = "text/xml, application/json"
        assert ApiClient.select_header_accept(accepts) == expected

    @pytest.mark.parametrize(
        ("content_type", "expected_output"),
        (
            (None, "application/json"),
            (["application/xml"], "application/xml"),
            (["application/xml", "text/plain"], "application/xml"),
            (["application/xml", "application/json"], "application/json"),
            (["application/xml", "*/*"], "application/json"),
        ),
        ids=[
            "defaults_to_json",
            "respects_single_option",
            "chooses_first_of_multiple",
            "defaults_to_json_if_available",
            "chooses_json_if_any_is_allowed",
        ],
    )
    def test_header_content_type(self, content_type, expected_output):
        assert ApiClient.select_header_content_type(content_type) == expected_output

    def get_example_params(self, param_type: str):
        if param_type == "dict":
            return {
                "Accept": ["text/plain", "application/json"],
                "Content-Type": "application/json",
            }
        else:
            return [
                ("Accept", ("text/plain", "application/json")),
                ("Content-Type", "application/json"),
            ]

    @pytest.mark.parametrize(
        ("collection_type", "separator"),
        (("ssv", " "), ("tsv", "\t"), ("pipes", "|"), ("csv", ","), ("default", ",")),
    )
    @pytest.mark.parametrize("input_type", ("dict", "tuple"))
    def test_params_to_tuples_from_dict(self, collection_type, separator, input_type):
        input_data = self.get_example_params(input_type)
        output = ApiClient.parameters_to_tuples(input_data, {"Accept": collection_type})
        output_dict = {}
        for entry in output:
            output_dict[entry[0]] = entry[1]
        assert output_dict["Content-Type"] == "application/json"
        assert output_dict["Accept"] == separator.join(["text/plain", "application/json"])

    @pytest.mark.parametrize("input_type", ("dict", "tuple"))
    def test_params_to_tuples_from_dict_multi(self, input_type):
        input_data = self.get_example_params(input_type)
        output = ApiClient.parameters_to_tuples(input_data, {"Accept": "multi"})
        assert len(output) == 3
        assert ("Accept", "text/plain") in output
        assert ("Accept", "application/json") in output
        assert ("Content-Type", "application/json") in output

    def test_dict_params_to_tuples_no_format_info(self):
        input_data = {"Accept": "application/json", "Content-Type": "application/json"}
        output = ApiClient.parameters_to_tuples(input_data, None)
        assert len(output) == 2
        assert ("Accept", "application/json") in output
        assert ("Content-Type", "application/json") in output

    def test_tuple_params_to_tuples_no_format_info(self):
        input_data = [
            ("Accept", "application/json"),
            ("Content-Type", "application/json"),
        ]
        output = ApiClient.parameters_to_tuples(input_data, None)
        assert len(output) == 2
        assert ("Accept", "application/json") in output
        assert ("Content-Type", "application/json") in output

    @pytest.fixture
    def file_context(self):
        file_name_list = []
        file_contents_list = []

        def create_files_for_test(
            file_count: int,
        ) -> Tuple[Iterable[str], Iterable[bytes]]:
            for file_index in range(0, file_count):
                fd, path = tempfile.mkstemp()
                os.close(fd)
                file_contents = secrets.token_bytes(32)
                with open(path, "wb") as f:
                    f.write(file_contents)
                file_name_list.append(path)
                file_contents_list.append(file_contents)
            return file_name_list, file_contents_list

        yield create_files_for_test

        for file_name in file_name_list:
            os.remove(file_name)

    @pytest.fixture
    def opened_file_context(self, file_context):
        file_name_list: List[str] = []
        file_handle_list: List[IO] = []
        file_contents_list: List[bytes] = []

        def create_files_for_test(
            file_count: int,
        ) -> Tuple[Iterable[IO], Iterable[str], Iterable[bytes]]:
            for file_index in range(0, file_count):
                fd, path = tempfile.mkstemp()
                os.close(fd)
                file_contents = secrets.token_bytes(32)
                with open(path, "wb") as f:
                    f.write(file_contents)
                file_name_list.append(path)
                file_contents_list.append(file_contents)
                file_handle_list.append(open(path, "rb"))
            return file_handle_list, file_name_list, file_contents_list

        yield create_files_for_test

        for file_handle in file_handle_list:
            file_handle.close()

        for file_name in file_name_list:
            os.remove(file_name)

    @pytest.mark.parametrize(
        "text_parameters",
        (
            None,
            [("clientId", "224ae34c")],
            [("clientId", "224ae34c"), ("nonce", "8acf453e")],
            [("clientId", b"224ae34c")],
            [("clientId", "224ae34c"), ("nonce", b"8acf453e")],
            [("clientId", b"224ae34c"), ("nonce", b"8acf453e")],
        ),
    )
    def test_prepare_post_parameters_with_text_parameters(self, text_parameters):
        if text_parameters is None:
            text_parameters = []

        output = ApiClient.prepare_post_parameters(text_parameters, None)

        assert len(list(output)) == len(text_parameters)
        for text_parameter in text_parameters:
            assert text_parameter in output

    @staticmethod
    def _check_file_contents(
        output: Iterable[Tuple[str, Union[str, bytes, Tuple[str, Union[str, bytes], str]]]],
        file_count: int,
        file_names: Iterable[str],
        file_contents: Iterable[bytes],
    ):
        assert len(list(output)) == file_count

        file_tuples = [parameter[1] for parameter in output if parameter[0] == "post_body"]
        for file_name, file_content in zip(file_names, file_contents):
            matched_parameter = [
                entry for entry in file_tuples if entry[0] == os.path.basename(file_name)
            ]
            assert len(matched_parameter) == 1
            assert matched_parameter[0][1] == file_content
            assert matched_parameter[0][2] is not None

    @pytest.mark.parametrize("file_parameter_count", (0, 1, 2))
    def test_prepare_post_parameters_with_file_names(self, file_context, file_parameter_count):
        file_names, file_contents = file_context(file_parameter_count)
        file_dict = {"post_body": file_names}

        output = ApiClient.prepare_post_parameters(None, file_dict)

        TestStaticMethods._check_file_contents(
            output, file_parameter_count, file_names, file_contents
        )

    @pytest.mark.parametrize("file_parameter_count", (1, 2, 3))
    def test_prepare_post_parameters_with_file_handles(
        self, opened_file_context, file_parameter_count
    ):
        file_handles, file_names, file_contents = opened_file_context(file_parameter_count)
        file_dict = {"post_body": file_handles}

        output = ApiClient.prepare_post_parameters(None, file_dict)

        TestStaticMethods._check_file_contents(
            output, file_parameter_count, file_names, file_contents
        )

    @pytest.mark.parametrize(
        ("file_name", "mime_type"),
        [
            ("door.jpg", "image/jpeg"),
            ("door.png", "image/png"),
            ("door.tiff", "image/tiff"),
            ("test.csv", "text/csv"),
            ("test.json", "application/json"),
        ],
    )
    def test_process_file(self, file_name: str, mime_type: str):
        if sys.platform == "win32" and file_name == "test.csv":
            pytest.skip("Excel interferes with CSV mime type detection on windows")
        file_path = Path(__file__).parent / "files" / file_name
        with open(file_path, "rb") as fp:
            filename, _, mimetype = ApiClient._process_file(fp)
            assert filename == file_name
            assert mimetype == mime_type
