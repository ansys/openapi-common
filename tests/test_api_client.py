import copy
import datetime
import json
import os
from io import BytesIO
from typing import Dict

import pytest
from pytest_mock import mocker
import requests
from requests.packages.urllib3.response import HTTPResponse
from requests_mock.response import _IOReader, _FakeConnection
import secrets

from ansys.grantami.common import ApiClient, SessionConfiguration, ApiException

TEST_URL = 'http://localhost/api/v1.svc'
UA_STRING = 'Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:47.0) Gecko/20100101 Firefox/47.0'


@pytest.fixture
def blank_client():
    session = requests.Session()
    client = ApiClient(session, TEST_URL, SessionConfiguration())
    yield client


def test_repr(blank_client):
    assert TEST_URL in str(blank_client)
    assert type(blank_client).__name__ in str(blank_client)


def test_default_user_agent(blank_client):
    assert blank_client.user_agent == "Swagger-Codegen/1.0.0/python"


def test_set_user_agent(blank_client):
    blank_client.user_agent = UA_STRING
    assert blank_client.user_agent == UA_STRING
    assert blank_client.default_headers['User-Agent'] == UA_STRING


def test_default_default_headers(blank_client):
    assert len(blank_client.default_headers) == 1
    assert 'User-Agent' in blank_client.default_headers.keys()


def test_set_default_header(blank_client):
    test_header_value = secrets.token_hex(8)
    test_header_name = secrets.token_hex(8)
    assert test_header_name not in blank_client.default_headers
    blank_client.default_headers[test_header_name] = test_header_value
    assert test_header_name in blank_client.default_headers
    assert blank_client.default_headers[test_header_name.upper()] == test_header_value


class TestSerialization:
    _test_value_list = ['foo', int(2), 2., True]
    _test_value_types = [str, int, float, bool]

    @pytest.fixture(autouse=True)
    def _blank_client(self, blank_client):
        self._client = blank_client

    def test_serialize_none(self):
        assert self._client.sanitize_for_serialization(None) is None

    @pytest.mark.parametrize(
        ('value', 'type_'),
        (('foo', str), (b'\x66\x6f\x6f', bytes), (int(2), int), (2., float), (True, bool))
    )
    def test_serialize_primitive(self, value, type_):
        serialized_primitive = self._client.sanitize_for_serialization(value)
        assert isinstance(serialized_primitive, type_)
        assert serialized_primitive == value

    def test_serialize_list(self):
        serialized_list = self._client.sanitize_for_serialization(self._test_value_list)
        assert isinstance(serialized_list, list)
        assert len(serialized_list) == len(self._test_value_list)
        for value, source_value, type_ in zip(serialized_list, self._test_value_list, self._test_value_types):
            assert isinstance(value, type_)
            assert value == source_value

    def test_serialize_tuple(self):
        source_tuple = tuple(self._test_value_list)
        serialized_tuple = self._client.sanitize_for_serialization(source_tuple)
        assert isinstance(serialized_tuple, tuple)
        assert len(serialized_tuple) == len(source_tuple)
        for value, source_value, type_ in zip(serialized_tuple, source_tuple, self._test_value_types):
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
        model_instance = models.ExampleModel('foo', 3, False, ["It's", "a", "list"])
        model_dict = {
            'Boolean': False,
            'Integer': 3,
            'ListOfStrings': ["It's", "a", "list"],
            'String': 'foo'
        }
        serialized_model = self._client.sanitize_for_serialization(model_instance)
        assert serialized_model == model_dict


class TestDeserialization:
    _test_value_list = ['foo', int(2), 2., True]
    _test_value_types = [str, int, float, bool]

    @pytest.fixture(autouse=True)
    def _blank_client(self, blank_client):
        self._client = blank_client

    def test_deserialize_none(self):
        assert self._client._ApiClient__deserialize(None, "") is None

    @pytest.mark.parametrize(
        ('value', 'type_'),
        (('foo', str), (int(2), int), (2., float), (True, bool))
    )
    @pytest.mark.parametrize('use_type_string', (True, False))
    def test_deserialize_primitive(self, value, type_, use_type_string):
        if use_type_string:
            type_ref = type_.__name__
        else:
            type_ref = type_
        deserialized_primitive = self._client._ApiClient__deserialize(value, type_ref)
        assert isinstance(deserialized_primitive, type_)
        assert deserialized_primitive == value

    @pytest.mark.parametrize(('target_type', 'expected_result'), ((int, int(3)), (str, '3.1')))
    def test_deserialize_float_casts(self, target_type, expected_result):
        test_float = 3.1
        deserialized_object = self._client._ApiClient__deserialize(test_float, target_type)
        assert isinstance(deserialized_object, target_type)
        assert deserialized_object == expected_result

    def test_deserialize_bytes(self):
        source_bytes = b'\x66\x6f\x6f'
        deserialized_bytes = self._client._ApiClient__deserialize(source_bytes, bytes)
        assert isinstance(deserialized_bytes, bytes)
        assert deserialized_bytes == source_bytes

    def test_deserialize_list(self):
        source_list = ['Look', 'another', 'list']
        deserialized_list = self._client._ApiClient__deserialize(source_list, 'list[str]')
        assert isinstance(deserialized_list, list)
        assert deserialized_list == source_list

    def test_deserialize_dict(self):
        source_dict = {
            1: 'one',
            2: 'two',
            3: 'three'
        }
        deserialized_dict = self._client._ApiClient__deserialize(source_dict, 'dict(int, str)')
        assert isinstance(deserialized_dict, dict)
        assert deserialized_dict == source_dict

    def test_deserialize_dict_casts_ints(self):
        source_dict = {
            'one': 1.0,
            'two': 2.,
            'three': 3.1
        }
        deserialized_dict = self._client._ApiClient__deserialize(source_dict, 'dict(str, int)')
        assert isinstance(deserialized_dict, dict)
        for key, val in source_dict.items():
            assert key in deserialized_dict
            assert deserialized_dict[key] == int(val)

    @pytest.mark.parametrize('use_type_string', (True, False))
    def test_deserialize_date(self, use_type_string):
        source_date = datetime.date(2371, 4, 26)
        date_string = source_date.isoformat()
        if use_type_string:
            type_ref = 'date'
        else:
            type_ref = datetime.date
        deserialized_date = self._client._ApiClient__deserialize(date_string, type_ref)
        assert isinstance(deserialized_date, datetime.date)
        assert deserialized_date == source_date

    @pytest.mark.parametrize('object_type', ('date', 'datetime'))
    def test_invalid_date_like_throws(self, object_type):
        invalid_date = 'NOT-A-DATE'
        with pytest.raises(ApiException) as exception_info:
            _ = self._client._ApiClient__deserialize(invalid_date, object_type)
        assert invalid_date in exception_info.value.reason_phrase
        assert f"{object_type} object" in exception_info.value.reason_phrase

    @pytest.mark.parametrize('use_type_string', (True, False))
    def test_deserialize_datetime(self, use_type_string):
        source_datetime = datetime.datetime(2371, 4, 26, 4, 39, 21)
        datetime_string = source_datetime.isoformat()
        if use_type_string:
            type_ref = 'datetime'
        else:
            type_ref = datetime.datetime
        deserialized_datetime = self._client._ApiClient__deserialize(datetime_string, type_ref)
        assert isinstance(deserialized_datetime, datetime.datetime)
        assert deserialized_datetime == source_datetime

    @pytest.mark.parametrize('use_type_string', (True, False))
    def test_deserialize_model(self, use_type_string):
        from . import models
        self._client.setup_client(models)

        model_instance = models.ExampleModel('foo', 3, False, ["It's", "a", "list"])
        model_dict = {
            'Boolean': False,
            'Integer': 3,
            'ListOfStrings': ["It's", "a", "list"],
            'String': 'foo'
        }
        if use_type_string:
            type_ref = "ExampleModel"
        else:
            type_ref = models.ExampleModel
        deserialized_model = self._client._ApiClient__deserialize(model_dict, type_ref)
        assert isinstance(deserialized_model, models.ExampleModel)
        assert deserialized_model == model_instance


class TestResponseParsing:
    from requests.adapters import HTTPAdapter
    _http_adapter = HTTPAdapter()
    _connection = _FakeConnection()
    """Test handling of requests.Response objects based on response_type"""

    @pytest.fixture(autouse=True)
    def _blank_client(self, blank_client):
        self._client = blank_client

    def create_response(self, json_: Dict = None, text: str = None, content: bytes = None, headers=None, content_type='application/json'):
        body = _IOReader()
        if json_ is not None:
            text = json.dumps(json_)
        if text is not None:
            content = text.encode('utf-8')
        if content is not None:
            body = _IOReader(content)
        status = 200
        reason = "OK"
        if headers is None:
            headers = {}
        headers['Content-Type'] = content_type

        raw = HTTPResponse(status=status,
                           reason=reason,
                           headers=headers,
                           body=body or _IOReader(b''),
                           decode_content=False,
                           preload_content=False,
                           original_response=None)

        request = requests.Request()
        response = self._http_adapter.build_response(request, raw)
        response.connection = self._connection
        return response

    def test_json_parsed_as_json(self, mocker):
        data = {'one': 1, 'two': 2, 'three': 3}
        response = self.create_response(data)
        deserialize_mock = mocker.patch.object(ApiClient, '_ApiClient__deserialize')
        deserialize_mock.return_value = True
        _ = self._client.deserialize(response, dict)
        deserialize_mock.assert_called()
        deserialize_mock.assert_called_once_with(data, dict)

    def test_text_parsed_as_text(self, mocker):
        data = "This is some data this is definitely not json, it should be rendered as a string"
        response = self.create_response(text=data, content_type='text/plain')
        deserialize_mock = mocker.patch.object(ApiClient, '_ApiClient__deserialize')
        deserialize_mock.return_value = True
        _ = self._client.deserialize(response, "str")
        deserialize_mock.assert_called()
        deserialize_mock.assert_called_once_with(data, "str")

    def test_application_data_is_not_parsed(self, mocker):
        data = b"This is some data this is definitely not json, it should be rendered as application/octet-stream"
        response = self.create_response(content=data, content_type='application/octet-stream')
        deserialize_mock = mocker.patch.object(ApiClient, '_ApiClient__deserialize')
        deserialize_mock.return_value = True
        _ = self._client.deserialize(response, "bytes")
        deserialize_mock.assert_called()
        deserialize_mock.assert_called_once_with(data, "bytes")

    def test_file_with_no_name_is_saved(self):
        data = b"Here is some file data to save"
        response = self.create_response(content=data, content_type='application/octet-stream')
        file_path = self._client.deserialize(response, "file")
        assert os.path.exists(file_path)
        with open(file_path, 'rb') as output_file:
            saved_data = output_file.read()
        os.remove(file_path)
        assert saved_data == data

    def test_file_with_name_is_saved(self):
        data = b"Here is some file data to save"
        file_name = 'test.xml'

        response = self.create_response(content=data, headers={'Content-Disposition': f'filename="{file_name}"'}, content_type='application/octet-stream')
        file_path = self._client.deserialize(response, "file")

        assert os.path.exists(file_path)

        saved_name = os.path.basename(file_path)
        assert saved_name == file_name

        with open(file_path, 'rb') as output_file:
            saved_data = output_file.read()
        os.remove(file_path)

        assert saved_data == data

    def test_file_with_header_no_name_is_saved(self):
        data = b"Here is some file data to save"
        disposition = 'very-sad'

        response = self.create_response(content=data, headers={'Content-Disposition': disposition}, content_type='application/octet-stream')
        file_path = self._client.deserialize(response, "file")

        assert os.path.exists(file_path)

        saved_name = os.path.basename(file_path)
        assert saved_name != disposition

        with open(file_path, 'rb') as output_file:
            saved_data = output_file.read()
        os.remove(file_path)

        assert saved_data == data


class TestRequestDispatch:
    """Test dispatching requests based on parameters and request name"""


class TestResponseHandling:
    """Test handling of responses and initial parsing"""


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
                (["application/xml", "*/*"], "application/json")
        ),
        ids=["defaults_to_json", "respects_single_option", "chooses_first_of_multiple",
             "defaults_to_json_if_available", "chooses_json_if_any_is_allowed"]
    )
    def test_header_content_type(self, content_type, expected_output):
        assert ApiClient.select_header_content_type(content_type) == expected_output

    def get_example_params(self, param_type: str):
        if param_type == "dict":
            return {"Accept": ["text/plain", "application/json"], "Content-Type": "application/json"}
        else:
            return ("Accept", ("text/plain", "application/json")), ("Content-Type", "application/json")

    @pytest.mark.parametrize(
        ("collection_type", "separator"),
        (
                ("ssv", " "),
                ("tsv", "\t"),
                ("pipes", "|"),
                ("csv", ","),
                ("default", ",")
        ))
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
