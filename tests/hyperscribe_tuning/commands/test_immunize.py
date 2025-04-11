from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.immunize import Immunize
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Immunize
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Immunize
    result = tested.schema_key()
    expected = "immunize"
    assert result == expected


def test_staged_command_extract():
    tested = Immunize
    tests = [
        ({}, None),
        ({
             "coding": {"text": "theImmunization"},
             "manufacturer": "theManufacturer",
             "sig_original": "theSig",
         }, CodedItem(label="theImmunization: theSig (theManufacturer)", code="", uuid="")),
        ({
             "coding": {"text": "theImmunization"},
             "manufacturer": "",
             "sig_original": "theSig",
         }, CodedItem(label="theImmunization: theSig (n/a)", code="", uuid="")),
        ({
             "coding": {"text": "theImmunization"},
             "manufacturer": "theManufacturer",
             "sig_original": "",
         }, CodedItem(label="theImmunization: n/a (theManufacturer)", code="", uuid="")),
        ({
             "coding": {"text": ""},
             "manufacturer": "theManufacturer",
             "sig_original": "theSig",
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
