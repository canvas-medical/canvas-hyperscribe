from datetime import datetime
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.update_goal import UpdateGoalCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.update_goal import UpdateGoal
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> UpdateGoal:
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
    return UpdateGoal(settings, cache, identification)


def test_class():
    tested = UpdateGoal
    assert issubclass(tested, Base)


def test_schema_key():
    tested = UpdateGoal
    result = tested.schema_key()
    expected = "updateGoal"
    assert result == expected


def test_note_section():
    tested = UpdateGoal
    result = tested.note_section()
    expected = "Plan"
    assert result == expected


def test_staged_command_extract():
    tested = UpdateGoal
    tests = [
        ({}, None),
        (
            {
                "due_date": "theDate",
                "priority": "thePriority",
                "progress": "theProgress",
                "goal_statement": {},
                "achievement_status": "theStatus",
            },
            None,
        ),
        (
            {
                "due_date": "theDate",
                "priority": "thePriority",
                "progress": "theProgress",
                "goal_statement": {"text": "theGoal"},
                "achievement_status": "theStatus",
            },
            CodedItem(label="theGoal: theProgress", code="", uuid=""),
        ),
        (
            {
                "due_date": "theDate",
                "priority": "thePriority",
                "progress": "",
                "goal_statement": {"text": "theGoal"},
                "achievement_status": "theStatus",
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


@patch.object(LimitedCache, "current_goals")
@patch.object(UpdateGoal, "add_code2description")
def test_command_from_json(add_code2description, current_goals):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        current_goals.reset_mock()
        chatter.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="123"),
        CodedItem(uuid="theUuid2", label="display2a", code="45"),
        CodedItem(uuid="theUuid3", label="display3a", code="9876"),
    ]
    tests = [
        (1, "theUuid2", [call("theUuid2", "display2a")]),
        (2, "theUuid3", [call("theUuid3", "display3a")]),
        (4, "", []),
    ]
    for idx, exp_uuid, exp_calls in tests:
        current_goals.side_effect = [goals, goals]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "previous_information": "thePreviousInformation",
            "parameters": {
                "goal": "display2a",
                "goalIndex": idx,
                "dueDate": "2025-02-03",
                "status": "improving",
                "priority": "medium-priority",
                "progressAndBarriers": "theProgressAndBarriers",
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = UpdateGoalCommand(
            goal_id=exp_uuid,
            due_date=datetime(2025, 2, 3),
            priority=UpdateGoalCommand.Priority.MEDIUM,
            achievement_status=UpdateGoalCommand.AchievementStatus.IMPROVING,
            progress="theProgressAndBarriers",
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        assert add_code2description.mock_calls == exp_calls
        calls = [call()]
        assert current_goals.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "goal": "",
        "goalIndex": -1,
        "dueDate": None,
        "status": "",
        "priority": "",
        "progressAndBarriers": "",
    }
    assert result == expected


@patch.object(LimitedCache, "current_goals")
def test_command_parameters_schemas(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    current_goals.side_effect = [goals]
    result = tested.command_parameters_schemas()
    expected = [
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "items": {
                "additionalProperties": False,
                "properties": {
                    "dueDate": {
                        "description": "Due date in YYYY-MM-DD format",
                        "format": "date",
                        "pattern": "^\\d{4}-\\d{2}-\\d{2}$",
                        "type": ["string", "null"],
                    },
                    "goal": {
                        "description": "The goal to update",
                        "enum": ["display1a", "display2a", "display3a"],
                        "type": "string",
                    },
                    "goalIndex": {
                        "description": "Index of the Goal to update",
                        "maximum": 2,
                        "minimum": 0,
                        "type": "integer",
                    },
                    "priority": {
                        "description": "Priority level of the goal",
                        "enum": ["high-priority", "medium-priority", "low-priority"],
                        "type": "string",
                    },
                    "progressAndBarriers": {
                        "description": "Progress or barriers, as free text",
                        "type": "string",
                    },
                    "status": {
                        "description": "Achievement status of the goal",
                        "enum": [
                            "in-progress",
                            "improving",
                            "worsening",
                            "no-change",
                            "achieved",
                            "sustaining",
                            "not-achieved",
                            "no-progress",
                            "not-attainable",
                        ],
                        "type": "string",
                    },
                },
                "required": [
                    "goal",
                    "goalIndex",
                    "dueDate",
                    "status",
                    "priority",
                    "progressAndBarriers",
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
    assert current_goals.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = "Change of status of a previously set goal, including progress, barriers, priority or due date."
    assert result == expected


@patch.object(LimitedCache, "current_goals")
def test_instruction_constraints(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    current_goals.side_effect = [goals]
    result = tested.instruction_constraints()
    expected = '"UpdateGoal" has to be related to one of the following goals: "display1a", "display2a", "display3a"'
    assert result == expected
    calls = [call()]
    assert current_goals.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_goals")
def test_is_available(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [(goals, True), ([], False)]
    for side_effect, expected in tests:
        current_goals.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        reset_mocks()
