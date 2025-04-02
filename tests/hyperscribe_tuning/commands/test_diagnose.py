from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.diagnose import Diagnose
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Diagnose
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Diagnose
    result = tested.schema_key()
    expected = "diagnose"
    assert result == expected


def test_staged_command_extract():
    tested = Diagnose
    tests = [
        ({}, None),
        ({
             "diagnose": {"text": "theDiagnosis", "value": "theCode"},
             "background": "theBackground",
             "today_assessment": "theAssessment",
         }, CodedItem(label="theDiagnosis (theAssessment)", code="theCode", uuid="")),
        ({
             "diagnose": {"text": "theDiagnosis", "value": "theCode"},
             "background": "theBackground",
             "today_assessment": "",
         }, CodedItem(label="theDiagnosis (n/a)", code="theCode", uuid="")),
        ({
             "diagnose": {"text": "", "value": "theCode"},
             "background": "theBackground",
             "today_assessment": "theAssessment",
         }, None),
        ({
             "diagnose": {"text": "theDiagnosis", "value": ""},
             "background": "theBackground",
             "today_assessment": "theAssessment",
         }, None),

    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
