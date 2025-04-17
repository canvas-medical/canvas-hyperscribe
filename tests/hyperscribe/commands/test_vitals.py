from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.vitals import VitalsCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.vitals import Vitals
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Vitals:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return Vitals(settings, cache, identification)


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
            code="",
            uuid="",
        )),
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
            code="",
            uuid="",
        )),
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
         }
        , None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(Vitals, "valid_or_none")
def test_command_from_json(valid_or_none):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        valid_or_none.reset_mock()

    tested = helper_instance()

    valid_or_none.side_effect = [
        50,  # height
        750,  # weight_lbs
        110,  # waist_circumference
        90,  # body_temperature
        150,  # blood_pressure_systole
        99,  # blood_pressure_diastole
        111,  # pulse
        33,  # respiration_rate
    ]

    arguments = {
        "uuid": "theUuid",
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "audits": ["theAudit"],
        "parameters": {
            "height": {"inches": 1},
            "weight": {"pounds": 2},
            "waistCircumference": {"centimeters": 3},
            "temperature": {"fahrenheit": 4.0},
            "bloodPressure": {"systolicPressure": 5, "diastolicPressure": 6},
            "pulseRate": {"beatPerMinute": 7},
            "respirationRate": {"beatPerMinute": 8},
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = VitalsCommand(
        height=50,
        weight_lbs=750,
        waist_circumference=110,
        body_temperature=90,
        blood_pressure_systole=150,
        blood_pressure_diastole=99,
        pulse=111,
        respiration_rate=33,
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [
        call(VitalsCommand, "height", 1),
        call(VitalsCommand, "weight_lbs", 2),
        call(VitalsCommand, "waist_circumference", 3),
        call(VitalsCommand, "body_temperature", 4),
        call(VitalsCommand, "blood_pressure_systole", 5),
        call(VitalsCommand, "blood_pressure_diastole", 6),
        call(VitalsCommand, "pulse", 7),
        call(VitalsCommand, "respiration_rate", 8),
    ]
    assert valid_or_none.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "height": {"inches": 0},
        "weight": {"pounds": 0},
        "waistCircumference": {"centimeters": 0},
        "temperature": {"fahrenheit": 0.0},
        "bloodPressure": {"systolicPressure": 0, "diastolicPressure": 0},
        "pulseRate": {"beatPerMinute": 0},
        "respirationRate": {"beatPerMinute": 0},
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Vital sign measurements (height, weight, waist circumference, temperature, blood pressure, pulse rate, respiration rate). "
                "All measurements should be combined in one instruction.")
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True


def test_valid_or_none():
    tested = Vitals
    tests = [
        ("height", 90, 90),
        ("height", 110, None),
        ("weight_lbs", 1000, 1000),
        ("weight_lbs", 2000, None),
    ]
    for field, value, expected in tests:
        result = tested.valid_or_none(VitalsCommand, field, value)
        if expected is None:
            assert result is None, f"--> {field}"
        else:
            assert result == value, f"--> {field} with {value}"
