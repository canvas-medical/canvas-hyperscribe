from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.prescription import Prescription
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Prescription
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Prescription
    result = tested.schema_key()
    expected = "prescribe"
    assert result == expected


def test_staged_command_extract():
    tested = Prescription
    tests = [
        ({}, None),
        ({
             "sig": "theSig",
             "refills": 2,
             "prescribe": {
                 "text": "theMedication",
                 "value": 292907,
             },
             "days_supply": 7,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": "allowed",
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": "3"
         }, CodedItem(
            label="theMedication: theSig (dispense: 3, supply days: 7, refills: 2, substitution: allowed, related conditions: theIndication1/theIndication2/theIndication3)",
            code="292907", uuid="")),
        ({
             "sig": "theSig",
             "refills": 2,
             "prescribe": {
                 "text": "",
                 "value": 292907,
             },
             "days_supply": 7,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": "allowed",
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": "3"
         }, None),
        ({
             "sig": "",
             "refills": None,
             "prescribe": {
                 "text": "theMedication",
                 "value": None,
             },
             "days_supply": None,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": None,
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": None
         }, CodedItem(
            label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, related conditions: theIndication1/theIndication2/theIndication3)",
            code="", uuid="")),
        ({
             "sig": "",
             "refills": None,
             "prescribe": {
                 "text": "theMedication",
                 "value": None,
             },
             "days_supply": None,
             "indications": [],
             "substitutions": None,
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": None
         }, CodedItem(label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, related conditions: n/a)", code="",
                      uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
