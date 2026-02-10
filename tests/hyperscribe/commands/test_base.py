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
    assert tested._template_permissions is None


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


# =========================================================================
# Template Integration Mixin Tests
# =========================================================================

FIXED_DATE = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)


def make_instruction(**overrides) -> InstructionWithParameters:
    """Create a standard InstructionWithParameters for template tests."""
    defaults = dict(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="theInformation",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )
    defaults.update(overrides)
    return InstructionWithParameters(**defaults)


def _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime):
    """Common setup for tests that exercise the LLM path."""
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    mock_datetime.now.return_value = FIXED_DATE


@patch("hyperscribe.commands.base.TemplatePermissions")
def test_template_permissions_property(mock_template_permissions):
    """Test lazy init and caching of TemplatePermissions."""
    tested = helper_instance()
    result1 = tested.template_permissions
    mock_template_permissions.assert_called_once_with("noteUuid")
    assert result1 is mock_template_permissions.return_value

    mock_template_permissions.reset_mock()
    result2 = tested.template_permissions
    assert result2 is result1
    mock_template_permissions.assert_not_called()


@pytest.mark.parametrize("return_val", [True, False])
@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_can_edit_field(mock_class_name, mock_tp, return_val):
    tested = helper_instance()
    mock_class_name.return_value = "TestCommand"
    mock_tp.return_value.can_edit_field.return_value = return_val
    assert tested.can_edit_field("narrative") is return_val
    mock_tp.return_value.can_edit_field.assert_called_once_with("TestCommand", "narrative")


@pytest.mark.parametrize("return_val", [["symptoms", "duration"], []])
@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_get_template_instructions(mock_class_name, mock_tp, return_val):
    tested = helper_instance()
    mock_class_name.return_value = "TestCommand"
    mock_tp.return_value.get_add_instructions.return_value = return_val
    assert tested.get_template_instructions("narrative") == return_val
    mock_tp.return_value.get_add_instructions.assert_called_once_with("TestCommand", "narrative")


@pytest.mark.parametrize("return_val", ["Patient is a [AGE] year old.", None])
@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_get_template_framework(mock_class_name, mock_tp, return_val):
    tested = helper_instance()
    mock_class_name.return_value = "TestCommand"
    mock_tp.return_value.get_edit_framework.return_value = return_val
    assert tested.get_template_framework("narrative") == return_val
    mock_tp.return_value.get_edit_framework.assert_called_once_with("TestCommand", "narrative")


# -- enhance_with_template_instructions ------------------------------------


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
def test_enhance_no_instructions_returns_original(
    mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    tested = helper_instance()
    mock_get_instructions.return_value = []
    instruction = make_instruction()

    result = tested.enhance_with_template_instructions("original", "narrative", instruction, MagicMock())

    assert result == "original"
    assert mock_json_schema.mock_calls == []


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
def test_enhance_with_instructions_calls_llm(mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime):
    chatter = MagicMock()
    instruction = make_instruction(information="Patient reports headache for 3 days.")
    tested = helper_instance()
    mock_get_instructions.return_value = ["symptoms", "duration"]
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [{"enhancedContent": "Enhanced: headache x3d"}]

    result = tested.enhance_with_template_instructions("original", "narrative", instruction, chatter)

    assert result == "Enhanced: headache x3d"
    assert chatter.single_conversation.called


@pytest.mark.parametrize("llm_response", [[], [{"enhancedContent": ""}]])
@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
def test_enhance_llm_empty_returns_original(
    mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime, llm_response
):
    chatter = MagicMock()
    tested = helper_instance()
    mock_get_instructions.return_value = ["symptoms"]
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = llm_response

    result = tested.enhance_with_template_instructions("original", "narrative", make_instruction(), chatter)

    assert result == "original"


# -- fill_template_content -------------------------------------------------


@pytest.mark.parametrize("add_instructions", [[], ["symptoms", "duration"]])
@patch.object(Base, "enhance_with_template_instructions")
@patch.object(Base, "_resolve_framework")
@patch.object(Base, "get_template_instructions")
def test_fill_template_content_no_framework(
    mock_get_instructions, mock_resolve_framework, mock_enhance, add_instructions
):
    """No framework → delegates to enhance_with_template_instructions."""
    chatter = MagicMock()
    instruction = make_instruction()
    tested = helper_instance()
    mock_resolve_framework.return_value = None
    mock_get_instructions.return_value = add_instructions
    mock_enhance.return_value = "enhanced content"

    result = tested.fill_template_content("generated", "narrative", instruction, chatter)

    assert result == "enhanced content"
    mock_enhance.assert_called_once_with("generated", "narrative", instruction, chatter)
    assert not chatter.single_conversation.called


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_with_framework(
    mock_resolve_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    chatter = MagicMock()
    instruction = make_instruction(information="Patient reports headache for 3 days.")
    tested = helper_instance()
    mock_resolve_framework.return_value = "Patient is a [AGE] year old [GENDER] presenting with [SYMPTOMS]."
    mock_get_instructions.return_value = ["symptoms", "duration"]
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [
        {"enhancedContent": "Patient is a 45 year old male presenting with headache x3d."}
    ]

    result = tested.fill_template_content("generated headache content", "narrative", instruction, chatter)

    assert result == "Patient is a 45 year old male presenting with headache x3d."
    assert chatter.single_conversation.called


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_strips_lit_markers(
    mock_resolve_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    chatter = MagicMock()
    instruction = make_instruction(information="Patient memory concerns noted.")
    tested = helper_instance()
    mock_resolve_framework.return_value = (
        "Patient presenting for assessment.\n"
        "{lit:Current concerns with memory:}\n"
        "{lit:Current concerns with functioning:}"
    )
    mock_get_instructions.return_value = []
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [{"enhancedContent": "filled content"}]

    tested.fill_template_content("generated", "narrative", instruction, chatter)

    user_prompt_text = "\n".join(chatter.single_conversation.call_args[0][1])
    assert "{lit:" not in user_prompt_text
    assert "Current concerns with memory:" in user_prompt_text
    assert "Current concerns with functioning:" in user_prompt_text


@patch.object(Base, "enhance_with_template_instructions")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_sub_only_uses_enhance_path(mock_resolve_framework, mock_get_instructions, mock_enhance):
    """Framework with only {sub:} + {add:} falls through to enhance path, not merge."""
    chatter = MagicMock()
    instruction = make_instruction(information="Exam findings.")
    tested = helper_instance()
    mock_resolve_framework.return_value = "{sub:Intact. No rashes.}{add:Replace with findings if available.}"
    mock_get_instructions.return_value = []
    mock_enhance.return_value = "enhanced content"

    result = tested.fill_template_content("generated", "narrative", instruction, chatter)

    assert result == "enhanced content"
    mock_enhance.assert_called_once_with(
        "generated",
        "narrative",
        instruction,
        chatter,
        extra_instructions=["Replace with findings if available."],
    )
    # The merge LLM call should NOT have been made
    assert not chatter.single_conversation.called


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_lit_plus_sub_preserves_lit(
    mock_resolve_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Framework with {lit:} + {sub:} keeps lit content and removes sub content."""
    chatter = MagicMock()
    instruction = make_instruction(information="Patient findings.")
    tested = helper_instance()
    mock_resolve_framework.return_value = "{lit:Section Header:}\n{sub:default text here}"
    mock_get_instructions.return_value = []
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [{"enhancedContent": "filled"}]

    tested.fill_template_content("generated", "narrative", instruction, chatter)

    user_prompt_text = "\n".join(chatter.single_conversation.call_args[0][1])
    assert "Section Header:" in user_prompt_text
    assert "default text here" not in user_prompt_text


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_extracts_add_markers(
    mock_resolve_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Inline {add:} markers are extracted from framework, stripped from display, and merged into instructions."""
    chatter = MagicMock()
    instruction = make_instruction(information="General exam findings noted.")
    tested = helper_instance()
    mock_resolve_framework.return_value = (
        "{lit:NAD. Well-developed, pleasant.}{add:Replace defaults with transcript findings if available.}"
    )
    mock_get_instructions.return_value = []
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [{"enhancedContent": "filled content"}]

    tested.fill_template_content("generated", "narrative", instruction, chatter)

    user_prompt_text = "\n".join(chatter.single_conversation.call_args[0][1])
    # {add:} markers should be stripped from the structured content
    assert "{add:" not in user_prompt_text
    # {lit:} markers should also be stripped
    assert "{lit:" not in user_prompt_text
    # The literal text should be present
    assert "NAD. Well-developed, pleasant." in user_prompt_text
    # The add instruction should appear in the instruction text
    assert "Replace defaults with transcript findings if available." in user_prompt_text


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_merges_add_markers_with_cache_instructions(
    mock_resolve_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Inline {add:} markers are merged with add_instructions from the cache field."""
    chatter = MagicMock()
    instruction = make_instruction(information="Patient findings.")
    tested = helper_instance()
    mock_resolve_framework.return_value = "Some framework text{add:inline instruction}"
    mock_get_instructions.return_value = ["cached instruction"]
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [{"enhancedContent": "filled"}]

    tested.fill_template_content("generated", "narrative", instruction, chatter)

    user_prompt_text = "\n".join(chatter.single_conversation.call_args[0][1])
    # Both sources of instructions should appear
    assert "cached instruction" in user_prompt_text
    assert "inline instruction" in user_prompt_text


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_with_framework_no_add_instructions(
    mock_resolve_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    chatter = MagicMock()
    tested = helper_instance()
    mock_resolve_framework.return_value = "Patient is presenting today."
    mock_get_instructions.return_value = []
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [{"enhancedContent": "Patient is presenting today with headache."}]

    result = tested.fill_template_content("generated", "narrative", make_instruction(), chatter)

    assert result == "Patient is presenting today with headache."


@pytest.mark.parametrize("llm_response", [[], [{"enhancedContent": ""}]])
@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_llm_empty_falls_back(
    mock_resolve_framework,
    mock_get_instructions,
    mock_json_schema,
    mock_demographic,
    mock_datetime,
    llm_response,
):
    chatter = MagicMock()
    tested = helper_instance()
    mock_resolve_framework.return_value = "Template structure here."
    mock_get_instructions.return_value = ["symptoms"]
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = llm_response

    result = tested.fill_template_content("generated content", "narrative", make_instruction(), chatter)

    assert result == "generated content"


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "_resolve_framework")
def test_fill_template_content_uses_existing_structure(
    mock_resolve_framework,
    mock_get_instructions,
    mock_json_schema,
    mock_demographic,
    mock_datetime,
):
    chatter = MagicMock()
    structured_content = (
        "Patient Name is a 46 year old male presenting for assessment.\n\n"
        "Current concerns with memory or cognition: Patient reports some memory issues.\n\n"
        "Current concerns with physical functioning: Patient reports stiffness."
    )
    instruction = make_instruction(information="Some prose from transcript")
    tested = helper_instance()
    mock_resolve_framework.return_value = structured_content
    mock_get_instructions.return_value = []
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [{"enhancedContent": "Updated structured content"}]

    tested.fill_template_content("generated prose", "narrative", instruction, chatter)

    prompt_text = " ".join(chatter.single_conversation.call_args[0][1])
    assert "Current concerns with memory or cognition" in prompt_text


# -- _resolve_framework ----------------------------------------------------


@patch.object(Base, "get_template_framework")
def test_resolve_framework_returns_cached_framework(mock_get_framework):
    tested = helper_instance()
    mock_get_framework.return_value = "Cached framework content"
    assert tested._resolve_framework("narrative") == "Cached framework content"
    mock_get_framework.assert_called_once_with("narrative")


# -- resolve_field ---------------------------------------------------------


@patch.object(Base, "fill_template_content")
@patch.object(Base, "can_edit_field")
def test_resolve_field_editable(mock_can_edit, mock_fill):
    instruction = make_instruction()
    chatter = MagicMock()
    tested = helper_instance()
    mock_can_edit.return_value = True
    mock_fill.return_value = "filled content"

    result = tested.resolve_field("narrative", "generated text", instruction, chatter)

    assert result == "filled content"
    mock_can_edit.assert_called_once_with("narrative")
    mock_fill.assert_called_once_with("generated text", "narrative", instruction, chatter)


@patch.object(Base, "fill_template_content")
@patch.object(Base, "can_edit_field")
def test_resolve_field_locked(mock_can_edit, mock_fill):
    tested = helper_instance()
    mock_can_edit.return_value = False

    result = tested.resolve_field("narrative", "text", make_instruction(), MagicMock())

    assert result is None
    mock_fill.assert_not_called()
