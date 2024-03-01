from ansys.openapi.common import Unset


def test_unset_repr():
    assert str(Unset) == "<Unset>"
