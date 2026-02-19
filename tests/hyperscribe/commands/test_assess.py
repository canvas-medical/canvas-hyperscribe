from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.assess import AssessCommand

from hyperscribe.commands.assess import Assess
from hyperscribe.commands.base import Base
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Assess:
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
    return Assess(settings, cache, identification)


def test_class():
    tested = Assess
    assert issubclass(tested, Base)


def test_command_type():
    tested = Assess
    result = tested.command_type()
    expected = "AssessCommand"
    assert result == expected


def test_schema_key():
    tested = Assess
    result = tested.schema_key()
    expected = "assess"
    assert result == expected


def test_note_section():
    tested = Assess
    result = tested.note_section()
    expected = "Assessment"
    assert result == expected


def test_staged_command_extract():
    tested = Assess
    tests = [
        ({}, None),
        ({"condition": {}, "narrative": "better", "background": "theBackground"}, None),
        (
            {
                "condition": {"text": "theCondition", "annotations": ["theCode"]},
                "narrative": "theNarrative",
                "background": "theBackground",
            },
            CodedItem(label="theCondition: theNarrative", code="", uuid=""),
        ),
        (
            {
                "condition": {"text": "theCondition", "annotations": ["theCode"]},
                "narrative": "",
                "background": "theBackground",
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


@patch.object(LimitedCache, "current_conditions")
@patch.object(Assess, "add_code2description")
def test_command_from_json(add_code2description, current_conditions):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        current_conditions.reset_mock()
        add_code2description.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (1, "theUuid2", [call("theUuid2", "display2a")]),
        (2, "theUuid3", [call("theUuid3", "display3a")]),
        (4, None, []),
    ]
    for idx, exp_uuid, exp_calls in tests:
        current_conditions.side_effect = [conditions, conditions]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "previous_information": "thePreviousInformation",
            "parameters": {
                "assessment": "theAssessment",
                "condition": "display2a",
                "conditionIndex": idx,
                "rationale": "theRationale",
                "status": "stable",
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = AssessCommand(
            condition_id=exp_uuid,
            background="theRationale",
            status=AssessCommand.Status.STABLE,
            narrative="theAssessment",
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        assert add_code2description.mock_calls == exp_calls
        assert chatter.mock_calls == []
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "condition": None,
        "conditionIndex": -1,
        "rationale": "",
        "status": "",
        "assessment": "",
    }
    assert result == expected


@patch.object(LimitedCache, "current_conditions")
def test_command_parameters_schemas(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.command_parameters_schemas()
    expected = [
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "items": {
                "additionalProperties": False,
                "properties": {
                    "assessment": {
                        "description": "Today's assessment of the condition, as free text",
                        "type": "string",
                    },
                    "condition": {
                        "description": "The condition to assess",
                        "enum": ["display1a", "display2a", "display3a", None],
                        "type": ["string", "null"],
                    },
                    "conditionIndex": {
                        "description": "Index of the Condition to assess, or -1",
                        "maximum": 2,
                        "minimum": -1,
                        "type": "integer",
                    },
                    "rationale": {
                        "description": "Rationale about the current assessment, as free text",
                        "type": "string",
                    },
                    "status": {
                        "description": "Status of the condition",
                        "enum": ["improved", "stable", "deteriorated"],
                        "type": "string",
                    },
                },
                "required": [
                    "condition",
                    "conditionIndex",
                    "rationale",
                    "status",
                    "assessment",
                ],
                "type": "object",
            },
            "maxItems": 1,
            "minItems": 1,
            "type": "array",
        },
    ]

    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_instruction_description(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_description()
    expected = (
        "Today's assessment of a diagnosed condition (display1a, display2a, display3a). "
        "There can be only one assessment per condition per instruction, "
        "and no instruction in the lack of."
    )
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_instruction_constraints(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_constraints()
    expected = (
        "'Assess' has to be related to one of the following conditions: "
        "display1a (ICD-10: CODE12.3), "
        "display2a (ICD-10: CODE45), "
        "display3a (ICD-10: CODE98.76)"
    )
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(Assess, "can_edit_field", return_value=True)
@patch.object(LimitedCache, "current_conditions")
def test_is_available(current_conditions, can_edit_field):
    def reset_mocks():
        current_conditions.reset_mock()
        can_edit_field.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [(conditions, True), ([], False)]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call("background"), call("narrative")]
        assert can_edit_field.mock_calls == calls
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()


@patch.object(Assess, "can_edit_field", return_value=False)
def test_is_available__all_fields_locked(can_edit_field):
    tested = helper_instance()
    result = tested.is_available()
    expected = False
    assert result == expected

    calls = [call("background"), call("narrative")]
    assert can_edit_field.mock_calls == calls


@patch.object(Assess, "can_edit_field")
@patch.object(LimitedCache, "current_conditions")
def test_is_available__partial_field_locked(current_conditions, can_edit_field):
    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
    ]
    tests = [
        ([True, False], True),
        ([False, True], True),
    ]
    for side_effect, expected in tests:
        can_edit_field.side_effect = side_effect
        current_conditions.side_effect = [conditions]
        result = tested.is_available()
        assert result is expected

        calls = [call("background"), call("narrative")]
        assert can_edit_field.mock_calls == calls
        calls = [call()]
        assert current_conditions.mock_calls == calls
        can_edit_field.reset_mock()
        current_conditions.reset_mock()
