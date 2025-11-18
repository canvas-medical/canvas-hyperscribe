from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from hyperscribe.commands.base import Base
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockClass


def helper_instance() -> Base:
    from hyperscribe.structures.custom_prompt import CustomPrompt

    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[
            CustomPrompt(command="Command1", prompt="Prompt1", active=True),
            CustomPrompt(command="Command2", prompt="Prompt2", active=True),
            CustomPrompt(command="Command3", prompt="Prompt3", active=False),
            CustomPrompt(command="Command4", prompt="", active=True),
        ],
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
    return Base(settings, cache, identification)


def test___init__():
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
    tested = Base(settings, cache, identification)
    assert tested.settings == settings
    assert tested.identification == identification
    assert tested.cache == cache
    assert tested._arguments_code2description == {}


def test_class_name():
    tested = Base
    result = tested.class_name()
    expected = "Base"
    assert result == expected


def test_schema_key():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.schema_key()


def test_note_section():
    tested = Base
    with pytest.raises(NotImplementedError):
        _ = tested.note_section()


def test_staged_command_extract():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.staged_command_extract({})


@patch.object(Base, "class_name")
def test_custom_prompt(class_name):
    def reset_mocks():
        class_name.reset_mock()

    tested = helper_instance()
    tests = [
        ("Command1", "Prompt1"),
        ("Command2", "Prompt2"),
        ("Command3", ""),  # <-- not active
        ("Command4", ""),
        ("Command5", ""),  # <--- unknown
    ]
    for class_name_side_effect, expected in tests:
        class_name.side_effect = [class_name_side_effect]
        result = tested.custom_prompt()
        assert result == expected, f"---> {class_name_side_effect}"

        calls = [call()]
        assert class_name.mock_calls == calls
        reset_mocks()


def test_command_from_json():
    chatter = MagicMock()
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        instruction = InstructionWithParameters(
            uuid="theUuid",
            index=7,
            instruction="theInstruction",
            information="theInformation",
            is_new=False,
            is_updated=True,
            previous_information="thePreviousInformation",
            parameters={"key": "value"},
        )
        _ = tested.command_from_json(instruction, chatter)
    assert chatter.mock_calls == []


def test_add_code2description():
    tested = helper_instance()
    assert tested._arguments_code2description == {}

    tested.add_code2description("code1", "description1")
    tested.add_code2description("code2", "description2")
    tested.add_code2description("code3", "description3")
    tested.add_code2description("code2", "description4")
    expected = {
        "code1": "description1",
        "code2": "description4",
        "code3": "description3",
    }
    assert tested._arguments_code2description == expected


@patch("hyperscribe.commands.base.InstructionWithSummary")
@patch.object(Base, "command_from_json")
def test_command_from_json_with_summary(command_from_json, instruction_with_summary):
    chatter = MagicMock()
    command = MagicMock(
        __class__=MockClass(__name__="theCommand"),
        values={
            "note_uuid": "theNoteUuid",
            "command_uuid": "theCommandUuid",
            "codeA": "valueA",
            "codeB": "valueB",
            "codeC": "valueC",
            "codeD": "valueD",
        },
    )

    def reset_mocks():
        command_from_json.reset_mock()
        instruction_with_summary.reset_mock()
        chatter.reset_mock()
        command.reset_mock()

    system_prompt = [
        "Medical context: create clinical charting shorthand summary (SOAP style) from JSON.",
        "JSON contains: command (detailed values), previousInformation (current), information (updated).",
        "",
        "Use medical abbreviations (CC, f/u, Dx, Rx, DC, VS, FHx, labs).",
        "Telegraphic, concise, for quick glance by knowledgeable person. Only new information. Max 20 words.",
    ]
    user_prompt = [
        "JSON:",
        "```json",
        '{"previousInformation": "thePreviousInformation", '
        '"information": "theInformation", '
        '"command": {'
        '"name": "theCommand", '
        '"attributes": {"codeA": "descriptionA", "codeB": "descriptionB", "codeD": "valueD"}}}',
        "```",
        "",
        "Return summary as JSON in Markdown code block:",
        "```json",
        '[{"summary": "shorthand summary"}]',
        "```",
        "",
    ]
    schemas = [
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 1,
            "maxItems": 1,
            "items": {
                "type": "object",
                "properties": {"summary": {"type": "string"}},
                "required": ["summary"],
                "additionalProperties": False,
            },
        },
    ]

    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )

    tested = helper_instance()

    # no command
    command_from_json.side_effect = [None]
    chatter.single_conversation.side_effect = []

    result = tested.command_from_json_with_summary(instruction, chatter)
    assert result is None

    calls = [call(instruction, chatter)]
    assert command_from_json.mock_calls == calls
    assert instruction_with_summary.mock_calls == []
    assert chatter.mock_calls == []
    assert command.mock_calls == []
    reset_mocks()

    # command generated
    instruction_with_command = InstructionWithCommand(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
        command=command,
    )
    # -- with chatter response
    command_from_json.side_effect = [instruction_with_command]
    chatter.single_conversation.side_effect = [[{"summary": "theSummary"}]]

    tested._arguments_code2description = {
        "valueA": "descriptionA",
        "valueB": "descriptionB",
        "valueC": "",
        "valueX": "descriptionX",
    }

    result = tested.command_from_json_with_summary(instruction, chatter)
    expected = instruction_with_summary.add_explanation.return_value
    assert result is expected

    calls = [call(instruction, chatter)]
    assert command_from_json.mock_calls == calls
    calls = [call.add_explanation(instruction=instruction_with_command, summary="theSummary")]
    assert instruction_with_summary.mock_calls == calls
    calls = [
        call.reset_prompts(),
        call.single_conversation(system_prompt, user_prompt, schemas, instruction),
    ]
    assert chatter.mock_calls == calls
    assert command.mock_calls == []
    reset_mocks()
    # -- no chatter response
    command_from_json.side_effect = [instruction_with_command]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json_with_summary(instruction, chatter)
    expected = instruction_with_summary.add_explanation.return_value
    assert result is expected

    calls = [call(instruction, chatter)]
    assert command_from_json.mock_calls == calls
    calls = [call.add_explanation(instruction=instruction_with_command, summary="")]
    assert instruction_with_summary.mock_calls == calls
    calls = [
        call.reset_prompts(),
        call.single_conversation(system_prompt, user_prompt, schemas, instruction),
    ]
    assert chatter.mock_calls == calls
    assert command.mock_calls == []
    reset_mocks()


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "custom_prompt")
def test_command_from_json_custom_prompted(custom_prompt, json_schema, demographic, mock_datetime):
    chatter = MagicMock()

    def reset_mocks():
        custom_prompt.reset_mock()
        json_schema.reset_mock()
        demographic.reset_mock()
        mock_datetime.reset_mock()
        chatter.reset_mock()

    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)

    system_prompt = [
        "Clinical encounter context: patient (theDemographic) and provider.",
        "Current time: 2025-11-04T04:55:21.012346+00:00",
        "",
        "Apply requested changes to data. Follow instructions exactly.",
        "IMPORTANT: Never add information not in original data. "
        "Better to keep unchanged than create incorrect information.",
    ]
    user_prompt = [
        "Original data:",
        "```text",
        "theData",
        "```",
        "",
        "Changes to apply:",
        "```text",
        "thePrompt",
        "```",
        "",
        "Return modified data as JSON in Markdown code block:",
        "```json",
        '[{"newData": "modified data"}]',
        "```",
        "",
    ]
    tested = helper_instance()

    # there is a custom prompt
    tests = [
        ([{"newData": "theNewData"}], "theNewData"),
        ([], "theData"),
    ]
    for chatter_side_effect, expected in tests:
        custom_prompt.side_effect = ["thePrompt"]
        json_schema.get.side_effect = [[{"the": "schema"}]]
        demographic.side_effect = ["theDemographic"]
        mock_datetime.now.side_effect = [date_0]
        chatter.single_conversation.side_effect = [chatter_side_effect]

        result = tested.command_from_json_custom_prompted("theData", chatter)
        assert result == expected

        calls = [call()]
        assert custom_prompt.mock_calls == calls
        calls = [call.get(["command_custom_prompt"])]
        assert json_schema.mock_calls == calls
        calls = [call(False)]
        assert demographic.mock_calls == calls
        calls = [call.now()]
        assert mock_datetime.mock_calls == calls
        calls = [call.single_conversation(system_prompt, user_prompt, [{"the": "schema"}], None)]
        assert chatter.mock_calls == calls
        reset_mocks()

    # there is NO custom prompt
    custom_prompt.side_effect = [""]
    json_schema.get.side_effect = []
    demographic.side_effect = []
    mock_datetime.now.side_effect = []
    chatter.single_conversation.side_effect = []

    result = tested.command_from_json_custom_prompted("theData", chatter)
    expected = "theData"
    assert result == expected

    calls = [call()]
    assert custom_prompt.mock_calls == calls
    assert json_schema.mock_calls == []
    assert demographic.mock_calls == []
    assert mock_datetime.mock_calls == []
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.command_parameters()


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 0
    result = schemas
    expected = []
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.instruction_description()


def test_instruction_constraints():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.instruction_constraints()


def test_is_available():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.is_available()
