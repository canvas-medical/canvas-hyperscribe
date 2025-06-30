from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from tests.helper import is_namedtuple


def test_class():
    tested = CaseExchangeSummary
    fields = {
        "title": str,
        "summary": str,
    }
    assert is_namedtuple(tested, fields)


def test_load_from_json():
    tested = CaseExchangeSummary
    result = tested.load_from_json([
        {"title": "theTitle1", "summary": "theSummary1"},
        {"title": "theTitle2", "summary": "theSummary2"},
        {"title": "theTitle3", "summary": "theSummary3"},
    ])
    expected = [
        CaseExchangeSummary(title="theTitle1", summary="theSummary1"),
        CaseExchangeSummary(title="theTitle2", summary="theSummary2"),
        CaseExchangeSummary(title="theTitle3", summary="theSummary3"),
    ]
    assert result == expected


def test_to_json():
    tested = CaseExchangeSummary(title="theTitle", summary="theSummary")
    result = tested.to_json()
    expected = {"title": "theTitle", "summary": "theSummary"}
    assert result == expected
