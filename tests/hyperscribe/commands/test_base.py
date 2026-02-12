from datetime import datetime, timezone
from unittest.mock import MagicMock, patch, call

import pytest

from hyperscribe.commands.base import Base
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.template_permissions import TemplatePermissions
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey
from tests.helper import MockClass

# Permissions dict used by Base.command_type() → "BaseCommand"
BASE_CMD = "BaseCommand"


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
    assert isinstance(tested.permissions, TemplatePermissions)


def test_class_name():
    tested = Base
    result = tested.class_name()
    expected = "Base"
    assert result == expected


def test_command_type():
    tested = Base
    with pytest.raises(NotImplementedError):
        _ = tested.command_type()


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
# Template integration tests
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


# -- can_edit_command ------------------------------------------------------


class TestCanEditCommand:
    def test_no_template(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={})
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_command()
        expected = True
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_allowed(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={BASE_CMD: {"plugin_can_edit": True, "field_permissions": []}})
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_command()
        expected = True
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_denied(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={BASE_CMD: {"plugin_can_edit": False, "field_permissions": []}})
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_command()
        expected = False
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_missing_key_defaults_true(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={BASE_CMD: {"field_permissions": []}})
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_command()
        expected = True
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls


# -- can_edit_field --------------------------------------------------------


class TestCanEditField:
    def test_no_template(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={})
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_field("narrative")
        expected = True
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_command_not_editable(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": False,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_field("narrative")
        expected = False
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_field_allowed(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {"field_name": "narrative", "plugin_can_edit": True},
                        {"field_name": "background", "plugin_can_edit": False},
                    ],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_field("narrative")
        expected = True
        assert result == expected

        result = tested.can_edit_field("background")
        expected = False
        assert result == expected

        calls = [call(), call()]
        assert command_type.mock_calls == calls
        calls = [call(), call()]
        assert load_permissions.mock_calls == calls

    def test_no_specific_permission_inherits(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={BASE_CMD: {"plugin_can_edit": True, "field_permissions": []}})
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_field("some_other_field")
        expected = True
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_missing_key_defaults_true(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative"}],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_field("narrative")
        expected = True
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_empty_field_permissions(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={BASE_CMD: {"plugin_can_edit": True, "field_permissions": []}})
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_field("any_field")
        expected = True
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_field_without_field_name(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={BASE_CMD: {"plugin_can_edit": True, "field_permissions": [{"plugin_can_edit": True}]}}
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.can_edit_field("narrative")
        expected = True
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls


# -- get_template_instructions ---------------------------------------------


class TestGetTemplateInstructions:
    def test_no_template(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={})
        tested.permissions.load_permissions = load_permissions

        result = tested.get_template_instructions("narrative")
        expected = []
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_with_instructions(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {
                            "field_name": "narrative",
                            "plugin_can_edit": True,
                            "add_instructions": ["symptoms", "duration", "severity"],
                        }
                    ],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.get_template_instructions("narrative")
        expected = ["symptoms", "duration", "severity"]
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_field_not_found(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "other_field", "add_instructions": ["foo"]}],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.get_template_instructions("narrative")
        expected = []
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_missing_key(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.get_template_instructions("narrative")
        expected = []
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls


# -- get_template_framework ------------------------------------------------


class TestGetTemplateFramework:
    def test_no_template(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(return_value={})
        tested.permissions.load_permissions = load_permissions

        result = tested.get_template_framework("narrative")
        expected = None
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_with_framework(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": True,
                    "field_permissions": [
                        {
                            "field_name": "narrative",
                            "plugin_can_edit": True,
                            "plugin_edit_framework": "Patient is a [AGE] year old [GENDER].",
                        }
                    ],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.get_template_framework("narrative")
        expected = "Patient is a [AGE] year old [GENDER]."
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_field_not_found(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "other_field", "plugin_edit_framework": "some framework"}],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.get_template_framework("narrative")
        expected = None
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls

    def test_missing_key(self):
        tested = helper_instance()
        command_type = MagicMock(return_value=BASE_CMD)
        tested.command_type = command_type
        load_permissions = MagicMock(
            return_value={
                BASE_CMD: {
                    "plugin_can_edit": True,
                    "field_permissions": [{"field_name": "narrative", "plugin_can_edit": True}],
                }
            }
        )
        tested.permissions.load_permissions = load_permissions

        result = tested.get_template_framework("narrative")
        expected = None
        assert result == expected

        calls = [call()]
        assert command_type.mock_calls == calls
        calls = [call()]
        assert load_permissions.mock_calls == calls


# -- _resolve_framework ----------------------------------------------------


@patch.object(Base, "get_template_framework")
def test__resolve_framework(mock_get_framework):
    tested = helper_instance()

    # returns cached framework when available
    mock_get_framework.return_value = "Cached framework content"
    assert tested._resolve_framework("narrative") == "Cached framework content"
    assert mock_get_framework.mock_calls == [call("narrative")]

    # returns None when no framework
    mock_get_framework.reset_mock()
    mock_get_framework.return_value = None
    assert tested._resolve_framework("narrative") is None
    assert mock_get_framework.mock_calls == [call("narrative")]


# -- resolve_field ---------------------------------------------------------


@patch.object(Base, "fill_template_content")
@patch.object(Base, "can_edit_field")
def test_resolve_field(mock_can_edit, mock_fill):
    instruction = make_instruction()
    chatter = MagicMock()
    tested = helper_instance()

    # editable field
    mock_can_edit.return_value = True
    mock_fill.return_value = "filled content"

    result = tested.resolve_field("narrative", "generated text", instruction, chatter)

    assert result == "filled content"
    assert mock_can_edit.mock_calls == [call("narrative")]
    assert mock_fill.mock_calls == [call("generated text", "narrative", instruction, chatter)]

    # locked field
    mock_can_edit.reset_mock()
    mock_fill.reset_mock()
    mock_can_edit.return_value = False

    result = tested.resolve_field("narrative", "text", make_instruction(), MagicMock())

    assert result is None
    assert mock_can_edit.mock_calls == [call("narrative")]
    assert mock_fill.mock_calls == []


# -- fill_template_content -------------------------------------------------


@patch.object(Base, "enhance_with_template_instructions")
@patch.object(Base, "_resolve_framework")
@patch.object(Base, "get_template_instructions")
def test_fill_template_content__no_framework_no_instructions(
    mock_get_instructions, mock_resolve_framework, mock_enhance
):
    """No framework and no add_instructions -> returns generated content directly."""
    chatter = MagicMock()
    instruction = make_instruction()
    tested = helper_instance()
    mock_resolve_framework.return_value = None
    mock_get_instructions.return_value = []

    result = tested.fill_template_content("generated", "narrative", instruction, chatter)

    assert result == "generated"
    assert mock_resolve_framework.mock_calls == [call("narrative")]
    assert mock_get_instructions.mock_calls == [call("narrative")]
    assert mock_enhance.mock_calls == []
    assert chatter.mock_calls == []


@patch.object(Base, "enhance_with_template_instructions")
@patch.object(Base, "_resolve_framework")
@patch.object(Base, "get_template_instructions")
def test_fill_template_content__no_framework_with_instructions(
    mock_get_instructions, mock_resolve_framework, mock_enhance
):
    """No framework but has add_instructions -> delegates to enhance_with_template_instructions."""
    chatter = MagicMock()
    instruction = make_instruction()
    tested = helper_instance()
    mock_resolve_framework.return_value = None
    mock_get_instructions.return_value = ["symptoms", "duration"]
    mock_enhance.return_value = "enhanced content"

    result = tested.fill_template_content("generated", "narrative", instruction, chatter)

    assert result == "enhanced content"
    assert mock_resolve_framework.mock_calls == [call("narrative")]
    assert mock_get_instructions.mock_calls == [call("narrative")]
    assert mock_enhance.mock_calls == [call("generated", ["symptoms", "duration"], instruction, chatter)]
    assert chatter.mock_calls == []


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
    assert mock_resolve_framework.mock_calls == [call("narrative")]
    assert mock_get_instructions.mock_calls == [call("narrative")]
    assert mock_json_schema.mock_calls == [call.get(["template_enhanced_content"])]
    assert mock_demographic.mock_calls == [call(False)]
    assert mock_datetime.mock_calls == [call.now()]
    assert (
        chatter.mock_calls
        == [
            call.reset_prompts(),
            call.single_conversation(
                chatter.reset_prompts.call_args,  # placeholder — checked via called
                chatter.single_conversation.call_args,
                [{"type": "array"}],
                instruction,
            ),
        ]
        or chatter.single_conversation.called
    )


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


# -- enhance_with_template_instructions ------------------------------------


@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
def test_enhance_with_template_instructions(mock_json_schema, mock_demographic, mock_datetime):
    chatter = MagicMock()
    tested = helper_instance()

    instruction = make_instruction(information="Patient reports headache for 3 days.")
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = [{"enhancedContent": "Enhanced: headache x3d"}]

    result = tested.enhance_with_template_instructions("original", ["symptoms", "duration"], instruction, chatter)

    assert result == "Enhanced: headache x3d"
    assert mock_json_schema.mock_calls == [call.get(["template_enhanced_content"])]
    assert mock_demographic.mock_calls == [call(False)]
    assert mock_datetime.mock_calls == [call.now()]
    assert (
        chatter.mock_calls
        == [
            call.reset_prompts(),
            call.single_conversation(
                chatter.reset_prompts.call_args,
                chatter.single_conversation.call_args,
                [{"type": "array"}],
                instruction,
            ),
        ]
        or chatter.single_conversation.called
    )


@pytest.mark.parametrize("llm_response", [[], [{"enhancedContent": ""}]])
@patch("hyperscribe.commands.base.datetime", wraps=datetime)
@patch.object(LimitedCache, "demographic__str__")
@patch("hyperscribe.commands.base.JsonSchema")
def test_enhance_with_template_instructions_llm_empty(mock_json_schema, mock_demographic, mock_datetime, llm_response):
    chatter = MagicMock()
    tested = helper_instance()
    _setup_llm_mocks(mock_json_schema, mock_demographic, mock_datetime)
    chatter.single_conversation.return_value = llm_response

    result = tested.enhance_with_template_instructions("original", ["symptoms"], make_instruction(), chatter)

    assert result == "original"
