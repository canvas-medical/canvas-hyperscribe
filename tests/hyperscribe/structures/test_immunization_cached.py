from datetime import date

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
