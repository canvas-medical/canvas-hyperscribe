from evaluations.structures.chart_item import ChartItem
from tests.helper import is_namedtuple


def test_class():
    tested = ChartItem
    fields = {
        "code": str,
        "label": str,
        "uuid": str,
    }
    assert is_namedtuple(tested, fields)


def test_to_json():
    tests = [
        (
            ChartItem(
                code="J45.9",
                label="Asthma, unspecified",
                uuid="a123e456-789b-0123-cdef-456789abcdef",
            ),
            {
                "code": "J45.9",
                "label": "Asthma, unspecified",
                "uuid": "a123e456-789b-0123-cdef-456789abcdef",
            },
        ),
        (
            ChartItem(code="", label="", uuid=""),
            {"code": "", "label": "", "uuid": ""},
        ),
    ]

    for tested, expected in tests:
        result = tested.to_json()
        assert result == expected


def test_load_from_json():
    tests = [
        (
            {
                "code": "E11.9",
                "label": "Type 2 diabetes mellitus without complications",
                "uuid": "d012e345-678f-9012-bcd3-456789abcdef",
            },
            ChartItem(
                code="E11.9",
                label="Type 2 diabetes mellitus without complications",
                uuid="d012e345-678f-9012-bcd3-456789abcdef",
            ),
        ),
        (
            {"code": "", "label": "", "uuid": ""},
            ChartItem(code="", label="", uuid=""),
        ),
    ]

    for data, expected in tests:
        result = ChartItem.load_from_json(data)
        assert result == expected
