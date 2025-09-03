from datetime import date
from unittest.mock import patch, call

from hyperscribe.structures.immunization_cached import ImmunizationCached
from tests.helper import is_namedtuple


def test_class():
    tested = ImmunizationCached
    fields = {
        "uuid": str,
        "label": str,
        "code_cpt": str,
        "code_cvx": str,
        "comments": str,
        "approximate_date": date,
    }
    assert is_namedtuple(tested, fields)


def test_to_dict():
    tested = ImmunizationCached(
        uuid="theUuid",
        label="theLabel",
        code_cpt="theCodeCpt",
        code_cvx="theCodeCvx",
        comments="theComments",
        approximate_date=date(2025, 7, 25),
    )
    result = tested.to_dict()
    expected = {
        "uuid": "theUuid",
        "label": "theLabel",
        "codeCpt": "theCodeCpt",
        "codeCvx": "theCodeCvx",
        "comments": "theComments",
        "approximateDate": "2025-07-25",
    }
    assert expected == result


def test_load_from_json():
    tested = ImmunizationCached
    result = tested.load_from_json(
        {
            "uuid": "theUuid",
            "label": "theLabel",
            "codeCpt": "theCodeCpt",
            "codeCvx": "theCodeCvx",
            "comments": "theComments",
            "approximateDate": "2025-07-25",
        }
    )
    expected = ImmunizationCached(
        uuid="theUuid",
        label="theLabel",
        code_cpt="theCodeCpt",
        code_cvx="theCodeCvx",
        comments="theComments",
        approximate_date=date(2025, 7, 25),
    )
    assert result == expected


@patch.object(ImmunizationCached, "load_from_json")
def test_load_from_json_list(load_from_json):
    def reset_mocks():
        load_from_json.reset_mock()

    tested = ImmunizationCached
    load_from_json.side_effect = ["item1", "item2", "item3"]
    result = tested.load_from_json_list([{"data": "value1"}, {"data": "value2"}, {"data": "value3"}])
    expected = ["item1", "item2", "item3"]
    assert result == expected

    calls = [
        call({"data": "value1"}),
        call({"data": "value2"}),
        call({"data": "value3"}),
    ]
    assert load_from_json.mock_calls == calls
    reset_mocks()
