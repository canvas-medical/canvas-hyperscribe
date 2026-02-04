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
# Template Permission Method Tests
# =========================================================================


@patch("hyperscribe.commands.base.TemplatePermissions")
def test_template_permissions_property(mock_template_permissions):
    """Test that template_permissions property lazily creates TemplatePermissions."""
    tested = helper_instance()

    # First access should create the instance
    result1 = tested.template_permissions

    # Verify TemplatePermissions was called with the note_uuid
    mock_template_permissions.assert_called_once_with("noteUuid")
    assert result1 is mock_template_permissions.return_value

    # Second access should return cached instance (no new calls)
    mock_template_permissions.reset_mock()
    result2 = tested.template_permissions
    assert result2 is result1
    mock_template_permissions.assert_not_called()


@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_can_edit_field(mock_class_name, mock_template_permissions):
    """Test can_edit_field delegates to template_permissions."""
    tested = helper_instance()

    mock_class_name.return_value = "TestCommand"
    mock_template_permissions.return_value.can_edit_field_by_class.return_value = True

    result = tested.can_edit_field("narrative")
    assert result is True

    calls = [call("TestCommand", "narrative")]
    assert mock_template_permissions.return_value.can_edit_field_by_class.mock_calls == calls


@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_can_edit_field_locked(mock_class_name, mock_template_permissions):
    """Test can_edit_field returns False when field is locked."""
    tested = helper_instance()

    mock_class_name.return_value = "TestCommand"
    mock_template_permissions.return_value.can_edit_field_by_class.return_value = False

    result = tested.can_edit_field("narrative")
    assert result is False


@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_get_template_instructions(mock_class_name, mock_template_permissions):
    """Test get_template_instructions delegates to template_permissions."""
    tested = helper_instance()

    mock_class_name.return_value = "TestCommand"
    mock_template_permissions.return_value.get_add_instructions_by_class.return_value = [
        "symptoms",
        "duration",
    ]

    result = tested.get_template_instructions("narrative")
    assert result == ["symptoms", "duration"]

    calls = [call("TestCommand", "narrative")]
    assert mock_template_permissions.return_value.get_add_instructions_by_class.mock_calls == calls


@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_get_template_instructions_empty(mock_class_name, mock_template_permissions):
    """Test get_template_instructions returns empty list when no instructions."""
    tested = helper_instance()

    mock_class_name.return_value = "TestCommand"
    mock_template_permissions.return_value.get_add_instructions_by_class.return_value = []

    result = tested.get_template_instructions("narrative")
    assert result == []


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
def test_enhance_with_template_instructions_no_instructions(
    mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Test enhance_with_template_instructions returns original content when no instructions."""
    chatter = MagicMock()
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
    mock_get_instructions.return_value = []

    result = tested.enhance_with_template_instructions("original content", "narrative", instruction, chatter)

    assert result == "original content"
    assert chatter.mock_calls == []
    assert mock_json_schema.mock_calls == []


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
def test_enhance_with_template_instructions_with_instructions(
    mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Test enhance_with_template_instructions uses LLM to incorporate instructions."""
    chatter = MagicMock()
    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="Patient reports headache for 3 days.",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )

    tested = helper_instance()
    mock_get_instructions.return_value = ["symptoms", "duration"]
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date_0
    chatter.single_conversation.return_value = [{"enhancedContent": "Enhanced: headache x3d"}]

    result = tested.enhance_with_template_instructions("original content", "narrative", instruction, chatter)

    assert result == "Enhanced: headache x3d"
    calls = [call.get(["template_enhanced_content"])]
    assert mock_json_schema.mock_calls == calls
    calls = [call.reset_prompts(), call.single_conversation(MagicMock(), MagicMock(), MagicMock(), instruction)]
    assert chatter.reset_prompts.called
    assert chatter.single_conversation.called


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
def test_enhance_with_template_instructions_llm_returns_empty(
    mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Test enhance_with_template_instructions returns original when LLM returns empty."""
    chatter = MagicMock()
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
    mock_get_instructions.return_value = ["symptoms"]
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date_0
    chatter.single_conversation.return_value = []

    result = tested.enhance_with_template_instructions("original content", "narrative", instruction, chatter)

    assert result == "original content"


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
def test_enhance_with_template_instructions_llm_returns_empty_string(
    mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Test enhance_with_template_instructions returns original when LLM returns empty string."""
    chatter = MagicMock()
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
    mock_get_instructions.return_value = ["symptoms"]
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date_0
    chatter.single_conversation.return_value = [{"enhancedContent": ""}]

    result = tested.enhance_with_template_instructions("original content", "narrative", instruction, chatter)

    assert result == "original content"


@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_get_template_framework(mock_class_name, mock_template_permissions):
    """Test get_template_framework delegates to template_permissions."""
    tested = helper_instance()

    mock_class_name.return_value = "TestCommand"
    mock_template_permissions.return_value.get_edit_framework_by_class.return_value = (
        "Patient is a [AGE] year old [GENDER]."
    )

    result = tested.get_template_framework("narrative")
    assert result == "Patient is a [AGE] year old [GENDER]."

    calls = [call("TestCommand", "narrative")]
    assert mock_template_permissions.return_value.get_edit_framework_by_class.mock_calls == calls


@patch("hyperscribe.commands.base.TemplatePermissions")
@patch.object(Base, "class_name")
def test_get_template_framework_no_framework(mock_class_name, mock_template_permissions):
    """Test get_template_framework returns None when no framework."""
    tested = helper_instance()

    mock_class_name.return_value = "TestCommand"
    mock_template_permissions.return_value.get_edit_framework_by_class.return_value = None

    result = tested.get_template_framework("narrative")
    assert result is None


@patch.object(Base, "enhance_with_template_instructions")
@patch.object(Base, "get_template_framework")
def test_fill_template_content_no_framework(mock_get_framework, mock_enhance):
    """Test fill_template_content calls enhance when no framework."""
    chatter = MagicMock()
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
    mock_get_framework.return_value = None
    mock_enhance.return_value = "enhanced content"

    result = tested.fill_template_content("generated content", "narrative", instruction, chatter)

    assert result == "enhanced content"
    calls = [call("narrative")]
    assert mock_get_framework.mock_calls == calls
    calls = [call("generated content", "narrative", instruction, chatter)]
    assert mock_enhance.mock_calls == calls


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "get_template_framework")
def test_fill_template_content_with_framework(
    mock_get_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Test fill_template_content uses LLM to fill template when framework exists."""
    chatter = MagicMock()
    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="Patient reports headache for 3 days.",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )

    tested = helper_instance()
    mock_get_framework.return_value = "Patient is a [AGE] year old [GENDER] presenting with [SYMPTOMS]."
    mock_get_instructions.return_value = ["symptoms", "duration"]
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date_0
    chatter.single_conversation.return_value = [
        {"enhancedContent": "Patient is a 45 year old male presenting with headache x3d."}
    ]

    result = tested.fill_template_content("generated headache content", "narrative", instruction, chatter)

    assert result == "Patient is a 45 year old male presenting with headache x3d."
    calls = [call.get(["template_enhanced_content"])]
    assert mock_json_schema.mock_calls == calls
    assert chatter.reset_prompts.called
    assert chatter.single_conversation.called


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "get_template_framework")
def test_fill_template_content_with_framework_no_add_instructions(
    mock_get_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Test fill_template_content works when framework exists but no add instructions."""
    chatter = MagicMock()
    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="Patient reports headache.",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )

    tested = helper_instance()
    mock_get_framework.return_value = "Patient is presenting today."
    mock_get_instructions.return_value = []  # No add instructions
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date_0
    chatter.single_conversation.return_value = [{"enhancedContent": "Patient is presenting today with headache."}]

    result = tested.fill_template_content("generated content", "narrative", instruction, chatter)

    assert result == "Patient is presenting today with headache."


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "get_template_framework")
def test_fill_template_content_llm_returns_empty(
    mock_get_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Test fill_template_content returns generated content when LLM returns empty."""
    chatter = MagicMock()
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
    mock_get_framework.return_value = "Template structure here."
    mock_get_instructions.return_value = ["symptoms"]
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date_0
    chatter.single_conversation.return_value = []

    result = tested.fill_template_content("generated content", "narrative", instruction, chatter)

    # Falls back to generated content
    assert result == "generated content"


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "get_template_framework")
def test_fill_template_content_llm_returns_empty_string(
    mock_get_framework, mock_get_instructions, mock_json_schema, mock_demographic, mock_datetime
):
    """Test fill_template_content returns generated content when LLM returns empty string."""
    chatter = MagicMock()
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
    mock_get_framework.return_value = "Template structure here."
    mock_get_instructions.return_value = ["symptoms"]
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date_0
    chatter.single_conversation.return_value = [{"enhancedContent": ""}]

    result = tested.fill_template_content("generated content", "narrative", instruction, chatter)

    # Falls back to generated content
    assert result == "generated content"


def test_has_structured_content_with_section_headers():
    """Test _has_structured_content detects section headers ending with colon only."""
    tested = helper_instance()

    # Content with section headers that END with colon (no content after colon on same line)
    # Using headers NOT in the known list to test the fallback line-by-line detection
    structured = """Patient Name is presenting for a visit.

Cardiovascular examination:
Heart sounds normal, no murmurs.

Respiratory examination:
Lungs clear bilaterally.

Neurological examination:
Alert and oriented."""

    assert tested._has_structured_content(structured) is True


def test_has_structured_content_with_inline_headers():
    """Test _has_structured_content detects inline header patterns."""
    tested = helper_instance()

    # Content with "Header: content" patterns
    structured = """Chief Complaint: Headache for 3 days
Duration: 3 days
Severity: Moderate
Associated symptoms: Nausea, light sensitivity"""

    assert tested._has_structured_content(structured) is True


def test_has_structured_content_prose_paragraph():
    """Test _has_structured_content returns False for plain prose."""
    tested = helper_instance()

    prose = (
        "The patient is a 46-year-old male presenting for a comprehensive geriatric assessment. "
        "He reports increasing frequency of tip-of-the-tongue phenomenon and difficulty recalling "
        "proper names of acquaintances. His family notes that he occasionally repeats questions "
        "within a 15-minute window."
    )

    assert tested._has_structured_content(prose) is False


def test_has_structured_content_invalid_header_patterns():
    """Test _has_structured_content rejects lines with colons that aren't valid headers."""
    tested = helper_instance()

    # Content with colons but invalid header patterns:
    # - lowercase prefixes (e.g., "the patient: something")
    # - very short prefixes (e.g., "a: something")
    # These should NOT be counted as headers
    content = """This is some content with colons that are not headers.

the patient: reports some symptoms here
a: small prefix that should not match
another lowercase: prefix example here

This is just regular text without structure."""

    assert tested._has_structured_content(content) is False


def test_has_structured_content_too_short():
    """Test _has_structured_content returns False for short content."""
    tested = helper_instance()

    assert tested._has_structured_content("Short") is False
    assert tested._has_structured_content("") is False


def test_has_structured_content_single_line():
    """Test _has_structured_content returns False for single line without known headers."""
    tested = helper_instance()

    single_line = "This is a single line of content without any structure."
    assert tested._has_structured_content(single_line) is False


def test_has_structured_content_known_template_headers_inline():
    """Test _has_structured_content detects known template headers even inline."""
    tested = helper_instance()

    # Content with known template section headers inline (no line breaks)
    # This mimics the geriatric assessment template format
    inline_structured = (
        "Arthur Henderson is a male patient presenting for a comprehensive geriatric assessment. "
        "Current concerns with memory or cognition: Patient reports feeling 'pretty sharp' and does "
        "crossword puzzles daily, but daughter reports he is repeating questions frequently. "
        "Current concerns with physical functioning: Patient reports morning knee stiffness. "
        "Patient history provided by: both patient and daughter."
    )

    assert tested._has_structured_content(inline_structured) is True


def test_has_structured_content_known_headers_case_insensitive():
    """Test _has_structured_content detects known headers case-insensitively."""
    tested = helper_instance()

    mixed_case = (
        "Patient presents today. CURRENT CONCERNS WITH MEMORY OR COGNITION: Some memory issues. "
        "current concerns with physical functioning: Mobility problems noted."
    )

    assert tested._has_structured_content(mixed_case) is True


def test_has_structured_content_memory_and_cognition_variation():
    """Test _has_structured_content detects 'and' variation of memory/cognition header."""
    tested = helper_instance()

    # The actual template may use "and" instead of "or"
    content = (
        "Arthur Henderson is an older male patient. "
        "Current concerns with memory and cognition: Maria reports Arthur is repeating questions. "
        "Current concerns with physical functioning: Arthur reports morning knee stiffness. "
        "Patient history provided by both Arthur and his daughter Maria."
    )

    assert tested._has_structured_content(content) is True


def test_has_structured_content_plan_template():
    """Test _has_structured_content detects Plan template structure."""
    tested = helper_instance()

    # Plan template with cognitive evaluation recommended header
    content = """Continue to follow up with PCP.

Cognitive evaluation recommended in: 6 months"""

    assert tested._has_structured_content(content) is True


def test_has_structured_content_single_known_header():
    """Test _has_structured_content detects even a single known header."""
    tested = helper_instance()

    # Content with just one known header should still be detected
    content = "Follow up with primary care in 2 weeks for blood pressure check."

    assert tested._has_structured_content(content) is True


def test_has_structured_content_inline_headers_not_known():
    """Test _has_structured_content detects inline headers that aren't in known list."""
    tested = helper_instance()

    # Content with "Header: content" patterns that aren't in the known headers list
    # This exercises the fallback line-by-line detection (line 457)
    content = """Medications Reviewed: All current prescriptions
Treatment Response: Good improvement noted
Side Effects: None reported
Blood Pressure: 120/80 mmHg"""

    assert tested._has_structured_content(content) is True


def test_has_structured_content_single_inline_header_insufficient():
    """Test _has_structured_content returns False for single inline header."""
    tested = helper_instance()

    # Content with only 1 inline header (not enough - needs 2+)
    # And no known headers
    content = """This is a description of the patient visit.
Patient presents for routine checkup. Medications Reviewed: Aspirin 81mg daily.
Everything else looks fine and patient is doing well."""

    # Should be False because only 1 inline header found (not 2+)
    assert tested._has_structured_content(content) is False


@patch("canvas_sdk.v1.data.note.Note")
@patch("hyperscribe.commands.base.get_schema_key")
def test_get_current_note_content_success(mock_get_schema_key, mock_note_class):
    """Test get_current_note_content reads content from the note."""
    tested = helper_instance()

    # Mock the schema_key lookup
    mock_get_schema_key.return_value = "hpi"

    # Mock the Note.objects.get() and commands query
    mock_note = MagicMock()
    mock_command = MagicMock()
    mock_command.data = {"narrative": "Structured content from note"}
    mock_note.commands.filter.return_value = [mock_command]
    mock_note_class.objects.get.return_value = mock_note

    result = tested.get_current_note_content("narrative")

    assert result == "Structured content from note"
    mock_note_class.objects.get.assert_called_once_with(id="noteUuid")
    mock_note.commands.filter.assert_called_once_with(schema_key="hpi")


@patch("hyperscribe.commands.base.get_schema_key")
def test_get_current_note_content_no_schema_key(mock_get_schema_key):
    """Test get_current_note_content returns None when no schema_key mapping."""
    tested = helper_instance()
    mock_get_schema_key.return_value = None

    result = tested.get_current_note_content("narrative")

    assert result is None


@patch("canvas_sdk.v1.data.note.Note")
@patch("hyperscribe.commands.base.get_schema_key")
def test_get_current_note_content_no_content(mock_get_schema_key, mock_note_class):
    """Test get_current_note_content returns None when no content found."""
    tested = helper_instance()
    mock_get_schema_key.return_value = "hpi"

    mock_note = MagicMock()
    mock_note.commands.filter.return_value = []  # No commands found
    mock_note_class.objects.get.return_value = mock_note

    result = tested.get_current_note_content("narrative")

    assert result is None


@patch("canvas_sdk.v1.data.note.Note")
@patch("hyperscribe.commands.base.get_schema_key")
def test_get_current_note_content_field_not_in_data(mock_get_schema_key, mock_note_class):
    """Test get_current_note_content when field_name not in command.data."""
    tested = helper_instance()
    mock_get_schema_key.return_value = "hpi"

    mock_note = MagicMock()
    mock_command = MagicMock()
    mock_command.data = {"other_field": "some content"}  # field_name not present
    mock_note.commands.filter.return_value = [mock_command]
    mock_note_class.objects.get.return_value = mock_note

    result = tested.get_current_note_content("narrative")

    assert result is None


@patch("canvas_sdk.v1.data.note.Note")
@patch("hyperscribe.commands.base.get_schema_key")
def test_get_current_note_content_command_data_none(mock_get_schema_key, mock_note_class):
    """Test get_current_note_content when command.data is None."""
    tested = helper_instance()
    mock_get_schema_key.return_value = "hpi"

    mock_note = MagicMock()
    mock_command = MagicMock()
    mock_command.data = None  # data is None
    mock_note.commands.filter.return_value = [mock_command]
    mock_note_class.objects.get.return_value = mock_note

    result = tested.get_current_note_content("narrative")

    assert result is None


@patch("canvas_sdk.v1.data.note.Note")
@patch("hyperscribe.commands.base.get_schema_key")
def test_get_current_note_content_empty_field_value(mock_get_schema_key, mock_note_class):
    """Test get_current_note_content when field value is empty."""
    tested = helper_instance()
    mock_get_schema_key.return_value = "hpi"

    mock_note = MagicMock()
    mock_command = MagicMock()
    mock_command.data = {"narrative": ""}  # Empty value
    mock_note.commands.filter.return_value = [mock_command]
    mock_note_class.objects.get.return_value = mock_note

    result = tested.get_current_note_content("narrative")

    assert result is None


@patch("canvas_sdk.v1.data.note.Note")
@patch("hyperscribe.commands.base.get_schema_key")
def test_get_current_note_content_handles_exception(mock_get_schema_key, mock_note_class):
    """Test get_current_note_content handles exceptions gracefully."""
    tested = helper_instance()
    mock_get_schema_key.return_value = "hpi"
    mock_note_class.objects.get.side_effect = Exception("Database error")

    result = tested.get_current_note_content("narrative")

    assert result is None


@patch.object(Base, "enhance_with_template_instructions")
@patch.object(Base, "_has_structured_content")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "get_template_framework")
@patch.object(Base, "get_current_note_content")
def test_fill_template_content_existing_content_no_structure(
    mock_get_note_content,
    mock_get_framework,
    mock_get_instructions,
    mock_has_structure,
    mock_enhance,
):
    """Test fill_template_content falls back to enhance when existing content has no structure."""
    chatter = MagicMock()

    # The actual note content is prose without structure
    prose_content = (
        "The patient is a 46-year-old male presenting for a comprehensive geriatric assessment. "
        "He reports increasing frequency of tip-of-the-tongue phenomenon."
    )

    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="Some prose from transcript",
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )

    tested = helper_instance()
    mock_get_framework.return_value = None  # No framework from cache
    mock_get_instructions.return_value = []
    mock_get_note_content.return_value = prose_content  # Note has content
    mock_has_structure.return_value = False  # But content has no structure
    mock_enhance.return_value = "enhanced content"

    result = tested.fill_template_content("generated prose", "narrative", instruction, chatter)

    # Should fall back to enhance_with_template_instructions
    assert result == "enhanced content"
    mock_enhance.assert_called_once_with("generated prose", "narrative", instruction, chatter)
    # Should NOT have called LLM directly for template filling
    assert not chatter.single_conversation.called


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
@patch.object(Base, "get_template_instructions")
@patch.object(Base, "get_template_framework")
@patch.object(Base, "get_current_note_content")
def test_fill_template_content_uses_existing_structure(
    mock_get_note_content,
    mock_get_framework,
    mock_get_instructions,
    mock_json_schema,
    mock_demographic,
    mock_datetime,
):
    """Test fill_template_content uses existing structured content when no framework from cache."""
    chatter = MagicMock()

    # The actual note content contains structured content (read from Canvas)
    structured_content = """Patient Name is a 46 year old male presenting for assessment.

Current concerns with memory or cognition: Patient reports some memory issues.

Current concerns with physical functioning: Patient reports stiffness."""

    instruction = InstructionWithParameters(
        uuid="theUuid",
        index=7,
        instruction="theInstruction",
        information="Some prose from transcript",  # This is from transcript, not the note
        is_new=False,
        is_updated=True,
        previous_information="thePreviousInformation",
        parameters={"key": "value"},
    )

    tested = helper_instance()
    mock_get_framework.return_value = None  # No framework from cache
    mock_get_instructions.return_value = []
    mock_get_note_content.return_value = structured_content  # Actual note has structure
    mock_json_schema.get.return_value = [{"type": "array"}]
    mock_demographic.return_value = "theDemographic"
    date_0 = datetime(2025, 11, 4, 4, 55, 21, 12346, tzinfo=timezone.utc)
    mock_datetime.now.return_value = date_0
    chatter.single_conversation.return_value = [{"enhancedContent": "Updated structured content"}]

    result = tested.fill_template_content("generated prose", "narrative", instruction, chatter)

    # Should have called LLM to merge content with the existing structure
    assert chatter.single_conversation.called
    call_args = chatter.single_conversation.call_args
    user_prompt = call_args[0][1]
    # The structured content should be in the prompt (as list items)
    prompt_text = " ".join(user_prompt)
    assert "Current concerns with memory or cognition" in prompt_text
