from hashlib import md5
import json
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.vitals import VitalsCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.vitals import Vitals
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
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
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
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


def test_note_section():
    tested = Vitals
    result = tested.note_section()
    expected = "Objective"
    assert result == expected


def test_staged_command_extract():
    tested = Vitals
    tests = [
        ({}, None),
        (
            {
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
                "blood_pressure_position_and_site": "1",
            },
            CodedItem(
                label="note: theNote, pulse: 67, height: 100, weight_oz: 4, weight_lbs: 180, pulse_rhythm: 0, "
                "body_temperature: 99, respiration_rate: 36, oxygen_saturation: 78, waist_circumference: 112, "
                "body_temperature_site: 1, blood_pressure_systole: 120, blood_pressure_diastole: 80, "
                "blood_pressure_position_and_site: 1",
                code="",
                uuid="",
            ),
        ),
        (
            {
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
                "blood_pressure_position_and_site": "1",
            },
            CodedItem(
                label="note: theNote, height: 100, weight_oz: 4, weight_lbs: 180, pulse_rhythm: 0, "
                "body_temperature: 99, waist_circumference: 112, body_temperature_site: 1, "
                "blood_pressure_position_and_site: 1",
                code="",
                uuid="",
            ),
        ),
        (
            {
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
                "blood_pressure_position_and_site": "",
            },
            None,
        ),
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
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "previous_information": "thePreviousInformation",
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
        "height": {"inches": None},
        "weight": {"pounds": None},
        "waistCircumference": {"centimeters": None},
        "temperature": {"fahrenheit": None},
        "bloodPressure": {"systolicPressure": None, "diastolicPressure": None},
        "pulseRate": {"beatPerMinute": None},
        "respirationRate": {"beatPerMinute": None},
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 1
    schema = schemas[0]

    #
    schema_hash = md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "5ab059e8d6ed14301a58a309b6cf77e4"
    assert schema_hash == expected_hash

    tests = [
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "",
        ),
        (
            [
                {
                    "height": {"inches": None},
                    "weight": {"pounds": None},
                    "waistCircumference": {"centimeters": None},
                    "temperature": {"fahrenheit": None},
                    "bloodPressure": {"systolicPressure": None, "diastolicPressure": None},
                    "pulseRate": {"beatPerMinute": None},
                    "respirationRate": {"beatPerMinute": None},
                }
            ],
            "",
        ),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                },
                {
                    "height": {"inches": 68},
                    "weight": {"pounds": 170},
                    "waistCircumference": {"centimeters": 90},
                    "temperature": {"fahrenheit": 99},
                    "bloodPressure": {"systolicPressure": 115, "diastolicPressure": 75},
                    "pulseRate": {"beatPerMinute": 70},
                    "respirationRate": {"beatPerMinute": 15},
                },
            ],
            "[{'height': {'inches': 70}, "
            "'weight': {'pounds': 180}, "
            "'waistCircumference': {'centimeters': 95}, "
            "'temperature': {'fahrenheit': 98}, "
            "'bloodPressure': {'systolicPressure': 120, 'diastolicPressure': 80}, "
            "'pulseRate': {'beatPerMinute': 72}, "
            "'respirationRate': {'beatPerMinute': 16}}, "
            "{'height': {'inches': 68}, "
            "'weight': {'pounds': 170}, "
            "'waistCircumference': {'centimeters': 90}, "
            "'temperature': {'fahrenheit': 99}, "
            "'bloodPressure': {'systolicPressure': 115, 'diastolicPressure': 75}, "
            "'pulseRate': {'beatPerMinute': 70}, "
            "'respirationRate': {'beatPerMinute': 15}}] is too long",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                    "extra": "field",
                }
            ],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        (
            [
                {
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "'height' is a required property, in path [0]",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "'weight' is a required property, in path [0]",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "'waistCircumference' is a required property, in path [0]",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "'temperature' is a required property, in path [0]",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "'bloodPressure' is a required property, in path [0]",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "'pulseRate' is a required property, in path [0]",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                }
            ],
            "'respirationRate' is a required property, in path [0]",
        ),
        (
            [
                {
                    "height": {"inches": 70, "extra": "field"},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120, "diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "Additional properties are not allowed ('extra' was unexpected), in path [0, 'height']",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"systolicPressure": 120},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "'diastolicPressure' is a required property, in path [0, 'bloodPressure']",
        ),
        (
            [
                {
                    "height": {"inches": 70},
                    "weight": {"pounds": 180},
                    "waistCircumference": {"centimeters": 95},
                    "temperature": {"fahrenheit": 98},
                    "bloodPressure": {"diastolicPressure": 80},
                    "pulseRate": {"beatPerMinute": 72},
                    "respirationRate": {"beatPerMinute": 16},
                }
            ],
            "'systolicPressure' is a required property, in path [0, 'bloodPressure']",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Vital sign measurements (height, weight, waist circumference, temperature, blood pressure, pulse rate, "
        "respiration rate). "
        "All measurements should be combined in one instruction."
    )
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
    tests = [("height", 90, 90), ("height", 110, None), ("weight_lbs", 1000, 1000), ("weight_lbs", 2000, None)]
    for field, value, expected in tests:
        result = tested.valid_or_none(VitalsCommand, field, value)
        if expected is None:
            assert result is None, f"--> {field}"
        else:
            assert result == value, f"--> {field} with {value}"
