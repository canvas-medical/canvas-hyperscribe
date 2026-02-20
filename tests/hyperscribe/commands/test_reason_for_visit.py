from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.reason_for_visit import ReasonForVisit
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance(structured_rfv: bool = False, custom_prompts: list[CustomPrompt] = None) -> ReasonForVisit:
    if custom_prompts is None:
        custom_prompts = []
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=structured_rfv,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=custom_prompts,
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
    return ReasonForVisit(settings, cache, identification)


def test_class():
    tested = ReasonForVisit
    assert issubclass(tested, Base)


def test_command_type():
    tested = ReasonForVisit
    result = tested.command_type()
    expected = "ReasonForVisitCommand"
    assert result == expected


def test_schema_key():
    tested = ReasonForVisit
    result = tested.schema_key()
    expected = "reasonForVisit"
    assert result == expected


def test_note_section():
    tested = ReasonForVisit
    result = tested.note_section()
    expected = "Subjective"
    assert result == expected


def test_staged_command_extract():
    tested = ReasonForVisit
    tests = [
        ({}, None),
        (
            {"coding": {"text": "theStructuredRfV"}, "comment": "theComment"},
            CodedItem(label="theStructuredRfV", code="", uuid=""),
        ),
        ({"coding": {"text": ""}, "comment": "theComment"}, CodedItem(label="theComment", code="", uuid="")),
        ({"coding": {"text": ""}, "comment": ""}, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "existing_reason_for_visits")
@patch.object(ReasonForVisit, "add_code2description")
def test_command_from_json(add_code2description, existing_reason_for_visits):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        existing_reason_for_visits.reset_mock()
        chatter.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_reason_for_visits.side_effect = []
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "previous_information": "thePreviousInformation",
        "parameters": {"comment": "theComment"},
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = ReasonForVisitCommand(comment="theComment", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert add_code2description.mock_calls == []
    assert existing_reason_for_visits.mock_calls == []
    assert chatter.mock_calls == []
    reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    tests = [
        (1, "theUuid2", True, [call("theUuid2", "display2")]),
        (2, "theUuid3", True, [call("theUuid3", "display3")]),
        (4, None, False, []),
    ]
    for idx, exp_uuid, exp_structured, exp_calls in tests:
        existing_reason_for_visits.side_effect = [reason_for_visits]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "previous_information": "thePreviousInformation",
            "parameters": {
                "comment": "theComment",
                "reasonForVisit": "theReasonForVisit",
                "reasonForVisitIndex": idx,
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = ReasonForVisitCommand(comment="theComment", note_uuid="noteUuid")
        if exp_structured:
            command.structured = exp_structured
        if exp_uuid:
            command.coding = exp_uuid
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        assert add_code2description.mock_calls == exp_calls
        calls = [call()]
        assert existing_reason_for_visits.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_command_parameters(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    tests = [
        (False, {"comment": ""}),
        (True, {"comment": "", "reasonForVisit": "", "reasonForVisitIndex": -1}),
    ]
    for rfv, expected in tests:
        tested = helper_instance(structured_rfv=rfv)
        existing_reason_for_visits.side_effect = []
        result = tested.command_parameters()
        assert result == expected
        assert existing_reason_for_visits.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_command_parameters_schemas(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_reason_for_visits.side_effect = []
    result = tested.command_parameters_schemas()
    expected = [
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "items": {
                "additionalProperties": False,
                "properties": {
                    "comment": {
                        "description": "extremely concise description of the reason or impetus "
                        "for the visit, as free text",
                        "type": "string",
                    },
                },
                "required": ["comment"],
                "type": "object",
            },
            "maxItems": 1,
            "minItems": 1,
            "type": "array",
        },
    ]

    assert result == expected
    assert existing_reason_for_visits.mock_calls == []
    reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    existing_reason_for_visits.side_effect = [reason_for_visits]
    result = tested.command_parameters_schemas()
    expected = [
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "items": {
                "additionalProperties": False,
                "properties": {
                    "comment": {
                        "description": "extremely concise description of the reason or impetus "
                        "for the visit, as free text",
                        "type": "string",
                    },
                    "reasonForVisit": {
                        "enum": ["display1", "display2", "display3"],
                        "type": "string",
                    },
                    "reasonForVisitIndex": {"type": "integer"},
                },
                "required": ["reasonForVisit", "reasonForVisitIndex", "comment"],
                "type": "object",
            },
            "maxItems": 1,
            "minItems": 1,
            "type": "array",
        },
    ]

    assert result == expected
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_instruction_description(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    # without custom prompt
    tests = [False, True]
    for rfv in tests:
        tested = helper_instance(structured_rfv=rfv)
        existing_reason_for_visits.side_effect = []
        result = tested.instruction_description()
        expected = (
            "Patient's stated reason and/or the prompting circumstance for the visit. "
            "There can be multiple reasons within an instruction, "
            "but only one such instruction in the whole discussion. "
            "So, if one was already found, simply update it by intelligently merging all reasons. "
            "It is important to report it upon identification."
        )
        assert result == expected
        reset_mocks()
    #
    # with custom prompt
    for rfv in tests:
        tested = helper_instance(
            structured_rfv=rfv,
            custom_prompts=[
                CustomPrompt(
                    command="ReasonForVisit",
                    prompt="custom prompt text",
                    active=True,
                )
            ],
        )
        existing_reason_for_visits.side_effect = []
        result = tested.instruction_description()
        expected = (
            "Patient's stated reason and/or the prompting circumstance for the visit. "
            "There can be multiple reasons within an instruction, "
            "but only one such instruction in the whole discussion. "
            "So, if one was already found, simply update it by intelligently merging all reasons. "
            "It is important to report it upon identification."
            "For documentation purposes, always include the relevant parts of the transcript for reference, "
            "including any previous sections when merging."
        )
        assert result == expected
        assert existing_reason_for_visits.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_instruction_constraints(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    tests = [False, True]
    for rfv in tests:
        tested = helper_instance(structured_rfv=rfv)
        existing_reason_for_visits.side_effect = []
        result = tested.instruction_constraints()
        expected = ""
        assert result == expected
        assert existing_reason_for_visits.mock_calls == []
        reset_mocks()


@patch.object(ReasonForVisit, "can_edit_field", return_value=True)
@patch.object(LimitedCache, "existing_reason_for_visits")
def test_is_available(existing_reason_for_visits, can_edit_field):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()
        can_edit_field.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_reason_for_visits.side_effect = []
    result = tested.is_available()
    assert result is True
    assert existing_reason_for_visits.mock_calls == []
    calls = [call("comment")]
    assert can_edit_field.mock_calls == calls
    reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    # -- no reason for visit defined
    existing_reason_for_visits.side_effect = [[]]
    result = tested.is_available()
    assert result is False
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    calls = [call("comment")]
    assert can_edit_field.mock_calls == calls
    reset_mocks()
    # -- some reasons for visit defined
    existing_reason_for_visits.side_effect = [reason_for_visits]
    result = tested.is_available()
    assert result is True
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    calls = [call("comment")]
    assert can_edit_field.mock_calls == calls
    reset_mocks()


@patch.object(ReasonForVisit, "can_edit_field", return_value=False)
def test_is_available__all_fields_locked(can_edit_field):
    tested = helper_instance()
    result = tested.is_available()
    expected = False
    assert result == expected

    calls = [call("comment")]
    assert can_edit_field.mock_calls == calls
