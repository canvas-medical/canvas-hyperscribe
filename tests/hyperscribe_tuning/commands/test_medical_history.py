from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.medical_history import MedicalHistory
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = MedicalHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = MedicalHistory
    result = tested.schema_key()
    expected = "medicalHistory"
    assert result == expected


def test_staged_command_extract():
    tested = MedicalHistory
    tests = [
        ({}, None),
        ({
             "comments": "theComment",
             "approximate_end_date": {"date": "endDate"},
             "past_medical_history": {"text": "theCondition"},
             "approximate_start_date": {"date": "startDate"},
         }, CodedItem(label="theCondition: from startDate to endDate (theComment)", code="", uuid="")),
        ({
             "comments": "theComment",
             "approximate_end_date": {"date": "endDate"},
             "past_medical_history": {"text": ""},
             "approximate_start_date": {"date": "startDate"},
         }, None),
        ({
             "comments": "",
             "approximate_end_date": {"date": "endDate"},
             "past_medical_history": {"text": "theCondition"},
             "approximate_start_date": {"date": "startDate"},
         }, CodedItem(label="theCondition: from startDate to endDate (n/a)", code="", uuid="")),
        ({
             "comments": "theComment",
             "approximate_end_date": {"date": "endDate"},
             "past_medical_history": {"text": "theCondition"},
             "approximate_start_date": {"date": ""},
         }, CodedItem(label="theCondition: from n/a to endDate (theComment)", code="", uuid="")),
        ({
             "comments": "theComment",
             "approximate_end_date": {"date": ""},
             "past_medical_history": {"text": "theCondition"},
             "approximate_start_date": {"date": "startDate"},
         }, CodedItem(label="theCondition: from startDate to n/a (theComment)", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
