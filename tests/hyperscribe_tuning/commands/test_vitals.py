from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.vitals import Vitals
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Vitals
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Vitals
    result = tested.schema_key()
    expected = "vitals"
    assert result == expected


def test_staged_command_extract():
    tested = Vitals
    tests = [
        ({}, None),
        ({
             "note": "theNote",
             "pulse": 67,
             "height": "100",
             "weight_oz": "4",
             "weight_lbs": "180",
             "pulse_rhythm": "0",
             "body_temperature": "99",
             "respiration_rate": 36,
             "oxygen_saturation": 78,
             "waist_circumference": "112",
             "body_temperature_site": "1",
             "blood_pressure_systole": 120,
             "blood_pressure_diastole": 80,
             "blood_pressure_position_and_site": "1"
         }, CodedItem(
            label="note: theNote, pulse: 67, height: 100, weight_oz: 4, weight_lbs: 180, pulse_rhythm: 0, body_temperature: 99, respiration_rate: 36, oxygen_saturation: 78, waist_circumference: 112, body_temperature_site: 1, blood_pressure_systole: 120, blood_pressure_diastole: 80, blood_pressure_position_and_site: 1",
            code="", uuid="")),
        ({
             "note": "theNote",
             "pulse": None,
             "height": "100",
             "weight_oz": "4",
             "weight_lbs": "180",
             "pulse_rhythm": "0",
             "body_temperature": "99",
             "respiration_rate": None,
             "oxygen_saturation": None,
             "waist_circumference": "112",
             "body_temperature_site": "1",
             "blood_pressure_systole": None,
             "blood_pressure_diastole": None,
             "blood_pressure_position_and_site": "1"
         }, CodedItem(
            label="note: theNote, height: 100, weight_oz: 4, weight_lbs: 180, pulse_rhythm: 0, body_temperature: 99, waist_circumference: 112, body_temperature_site: 1, blood_pressure_position_and_site: 1",
            code="", uuid="")),
        ({
             "note": "",
             "pulse": None,
             "height": "",
             "weight_oz": "",
             "weight_lbs": "",
             "pulse_rhythm": "",
             "body_temperature": None,
             "respiration_rate": None,
             "oxygen_saturation": None,
             "waist_circumference": "",
             "body_temperature_site": "",
             "blood_pressure_systole": None,
             "blood_pressure_diastole": None,
             "blood_pressure_position_and_site": ""
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
