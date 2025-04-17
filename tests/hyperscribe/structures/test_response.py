from hyperscribe.structures.response import Response
from tests.helper import is_namedtuple


def test_class():
    tested = Response
    fields = {
        "dbid": int,
        "value": str | int,
        "selected": bool,
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tested = Response(dbid=123, value=456, selected=True)
    result = tested.to_json()
    expected = {"dbid": 123, "value": 456, "selected": True}
    assert result == expected
    #
    tested = Response(dbid=123, value="456", selected=False)
    result = tested.to_json()
    expected = {"dbid": 123, "value": "456", "selected": False}
    assert result == expected


def test_for_llm():
    tested = Response(dbid=123, value=456, selected=True)
    result = tested.for_llm()
    expected = {"responseId": 123, "value": 456, "selected": True}
    assert result == expected
    #
    tested = Response(dbid=123, value="456", selected=False)
    result = tested.for_llm()
    expected = {"responseId": 123, "value": "456", "selected": False}
    assert result == expected


def test_load_from():
    tested = Response
    #
    result = tested.load_from({"dbid": 123, "value": 456, "selected": True})
    expected = Response(dbid=123, value=456, selected=True)
    assert result == expected
    #
    result = tested.load_from({"dbid": 123, "value": "456", "selected": False})
    expected = Response(dbid=123, value="456", selected=False)
    assert result == expected


def test_load_from_llm():
    tested = Response
    #
    result = tested.load_from_llm({"responseId": 123, "value": 456, "selected": True})
    expected = Response(dbid=123, value=456, selected=True)
    assert result == expected
    #
    result = tested.load_from_llm({"responseId": 123, "value": "456", "selected": False})
    expected = Response(dbid=123, value="456", selected=False)
    assert result == expected
