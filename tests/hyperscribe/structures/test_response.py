from hyperscribe.structures.response import Response
from tests.helper import is_namedtuple


def test_class():
    tested = Response
    fields = {
        "dbid": int,
        "value": str | int,
        "selected": bool,
        "comment": str | None,
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tested = Response(dbid=123, value=456, selected=True, comment="theComment")
    result = tested.to_json()
    expected = {"dbid": 123, "value": 456, "selected": True, "comment": "theComment"}
    assert result == expected
    #
    tested = Response(dbid=123, value="456", selected=False, comment="theComment")
    result = tested.to_json()
    expected = {"dbid": 123, "value": "456", "selected": False, "comment": "theComment"}
    assert result == expected


def test_for_llm():
    tested = Response(dbid=123, value=456, selected=True, comment="theComment")
    result = tested.for_llm(False)
    expected = {"responseId": 123, "value": 456, "selected": True}
    assert result == expected
    result = tested.for_llm(True)
    expected = {
        "responseId": 123,
        "value": 456,
        "selected": True,
        "comment": "theComment",
        "description": "add in the comment key any relevant information expanding the answer",
    }
    assert result == expected
    #
    tested = Response(dbid=123, value="456", selected=False, comment="theComment")
    result = tested.for_llm(False)
    expected = {"responseId": 123, "value": "456", "selected": False}
    assert result == expected
    result = tested.for_llm(True)
    expected = {
        "responseId": 123,
        "value": "456",
        "selected": False,
        "comment": "theComment",
        "description": "add in the comment key any relevant information expanding the answer",
    }
    assert result == expected


def test_load_from():
    tested = Response
    #
    result = tested.load_from({"dbid": 123, "value": 456, "selected": True})
    expected = Response(dbid=123, value=456, selected=True, comment=None)
    assert result == expected
    result = tested.load_from({"dbid": 123, "value": 456, "selected": True, "comment": "theComment"})
    expected = Response(dbid=123, value=456, selected=True, comment="theComment")
    assert result == expected
    #
    result = tested.load_from({"dbid": 123, "value": "456", "selected": False, "comment": "theComment"})
    expected = Response(dbid=123, value="456", selected=False, comment="theComment")
    assert result == expected


def test_load_from_llm():
    tested = Response
    #
    result = tested.load_from_llm({"responseId": 123, "value": 456, "selected": True})
    expected = Response(dbid=123, value=456, selected=True, comment=None)
    assert result == expected
    result = tested.load_from_llm({"responseId": 123, "value": 456, "selected": True, "comment": "theComment"})
    expected = Response(dbid=123, value=456, selected=True, comment="theComment")
    assert result == expected
    #
    result = tested.load_from_llm({"responseId": 123, "value": "456", "selected": False, "comment": "theComment"})
    expected = Response(dbid=123, value="456", selected=False, comment="theComment")
    assert result == expected
