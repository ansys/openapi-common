from . import models

import pytest


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
