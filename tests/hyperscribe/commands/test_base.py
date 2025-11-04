import json
from datetime import datetime, timezone
from hashlib import md5
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
            CustomPrompt(command="Command1", prompt="Prompt1"),
            CustomPrompt(command="Command2", prompt="Prompt2"),
            CustomPrompt(command="Command3", prompt="Prompt3"),
            CustomPrompt(command="Command4", prompt=""),
        ],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
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
        ("Command3", "Prompt3"),
        ("Command4", ""),
        ("Command5", ""),
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
        "The conversation is in the medical context.",
        "The user will provide you with a JSON built for a medical software, including:",
        "- `command` providing accurate and detailed values",
        "- `previousInformation` a plain English description currently know by the software",
        "- `information` a plain English description built on top of `previousInformation`.",
        "",
        "Your task is to produce a summary in clinical charting shorthand style (like SOAP notes) out of this JSON.",
        "",
        "Use plain English with standard medical abbreviations (e.g., CC, f/u, Dx, Rx, DC, VS, FHx, labs).",
        "Be telegraphic, concise, and formatted like real chart notes for a quick glance from a knowledgeable person.",
        "Only new information should be included, and 20 words should be the maximum.",
    ]
    user_prompt = [
        "Here is a JSON intended to the medical software:",
        "```json",
        '{"previousInformation": "thePreviousInformation", '
        '"information": "theInformation", '
        '"command": {'
        '"name": "theCommand", '
        '"attributes": {"codeA": "descriptionA", "codeB": "descriptionB", "codeD": "valueD"}}}',
        "```",
        "",
        "Please, following the directions, present the summary of the new information only like "
        "this Markdown code block:",
        "```json",
        '[{"summary": "clinical charting shorthand style summary, '
        "minimal and limited to the new information but useful for "
        'a quick glance from a knowledgeable person"}]',
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
        parameters={"key": "value"},
    ).set_previous_information("thePreviousInformation")

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
        parameters={"key": "value"},
        command=command,
    ).set_previous_information("thePreviousInformation")
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
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
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
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
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
        "The conversation is in the context of a clinical encounter between "
        "patient (theDemographic) and licensed healthcare provider.",
        "",
        "The user will submit to you some data related to the conversation as well as how to modify it.",
        "It is important to follow the requested changes without never make things up.",
        "It is better to keep the data unchanged rather than create incorrect information.",
        "",
        "Please, note that now is 2025-11-04T04:55:21.012346+00:00.",
        "",
    ]
    user_prompt = [
        "Here is the original data:",
        "```text",
        "theData",
        "```",
        "",
        "Apply the following changes:",
        "```text",
        "thePrompt",
        "```",
        "",
        "Do NOT add information which is not explicitly provided in the original data.",
        "",
        "Fill the JSON object with the relevant information:",
        "```json",
        '[{"newData": ""}]',
        "```",
        "",
        "Your response must be a JSON Markdown block validated with the schema:",
        "```json",
        '{\n "the": "schema"\n}',
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
    result = tested.command_parameters_schemas()
    expected = "d751713988987e9331980363e24189ce"
    assert md5(json.dumps(result).encode()).hexdigest() == expected


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
