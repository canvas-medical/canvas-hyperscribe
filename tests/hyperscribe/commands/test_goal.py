from datetime import date
from hashlib import md5
import json
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.goal import GoalCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.goal import Goal
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Goal:
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
    return Goal(settings, cache, identification)


def test_class():
    tested = Goal
    assert issubclass(tested, Base)


def test_command_type():
    tested = Goal
    result = tested.command_type()
    expected = "GoalCommand"
    assert result == expected


def test_schema_key():
    tested = Goal
    result = tested.schema_key()
    expected = "goal"
    assert result == expected


def test_note_section():
    tested = Goal
    result = tested.note_section()
    expected = "Plan"
    assert result == expected


def test_staged_command_extract():
    tested = Goal
    tests = [
        ({}, None),
        (
            {
                "due_date": "2025-02-27",
                "priority": "medium-priority",
                "progress": "theProgress",
                "start_date": "2025-02-26",
                "goal_statement": "theGoal",
                "achievement_status": "improving",
            },
            CodedItem(label="theGoal", code="", uuid=""),
        ),
        (
            {
                "due_date": "2025-02-27",
                "priority": "medium-priority",
                "progress": "theProgress",
                "start_date": "2025-02-26",
                "goal_statement": "",
                "achievement_status": "improving",
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


def test_command_from_json():
    chatter = MagicMock()
    tested = helper_instance()
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "previous_information": "thePreviousInformation",
        "parameters": {
            "goal": "theGoal",
            "startDate": "2023-11-12",
            "dueDate": "2025-02-04",
            "status": "improving",
            "priority": "medium-priority",
            "progressAndBarriers": "theProgressAndBarriers",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = GoalCommand(
        goal_statement="theGoal",
        start_date=date(2023, 11, 12),
        due_date=date(2025, 2, 4),
        achievement_status=GoalCommand.AchievementStatus.IMPROVING,
        priority=GoalCommand.Priority.MEDIUM,
        progress="theProgressAndBarriers",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "goal": "",
        "startDate": None,
        "dueDate": None,
        "status": "",
        "priority": "",
        "progressAndBarriers": "",
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 1
    schema = schemas[0]

    #
    schema_hash = md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "9d02cf91dc6d2c1273ec05c4e8be1640"
    assert schema_hash == expected_hash

    tests = [
        (
            [
                {
                    "goal": "Lose 10 pounds",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Patient is motivated",
                }
            ],
            "",
        ),
        (
            [
                {
                    "goal": "Control blood sugar",
                    "startDate": None,
                    "dueDate": None,
                    "status": "in-progress",
                    "priority": "high-priority",
                    "progressAndBarriers": "Patient is compliant",
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
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                },
                {
                    "goal": "Exercise more",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "in-progress",
                    "priority": "high-priority",
                    "progressAndBarriers": "Started walking",
                },
            ],
            "[{'goal': 'Lose weight', "
            "'startDate': '2025-02-01', "
            "'dueDate': '2025-06-01', "
            "'status': 'improving', "
            "'priority': 'medium-priority', "
            "'progressAndBarriers': 'Motivated'}, "
            "{'goal': 'Exercise more', "
            "'startDate': '2025-02-01', "
            "'dueDate': '2025-06-01', "
            "'status': 'in-progress', "
            "'priority': 'high-priority', "
            "'progressAndBarriers': 'Started walking'}] is too long",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                    "extra": "field",
                }
            ],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        (
            [
                {
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'goal' is a required property, in path [0]",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'startDate' is a required property, in path [0]",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "status": "improving",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'dueDate' is a required property, in path [0]",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'status' is a required property, in path [0]",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'priority' is a required property, in path [0]",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "priority": "medium-priority",
                }
            ],
            "'progressAndBarriers' is a required property, in path [0]",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "invalid_status",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'invalid_status' is not one of "
            "['in-progress', 'improving', 'worsening', 'no-change', 'achieved', 'sustaining', "
            "'not-achieved', 'no-progress', 'not-attainable'], in path [0, 'status']",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "priority": "invalid_priority",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'invalid_priority' is not one of ['high-priority', 'medium-priority', 'low-priority'], "
            "in path [0, 'priority']",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "02-04-2025",
                    "dueDate": "2025-06-01",
                    "status": "improving",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'02-04-2025' does not match '^\\\\d{4}-\\\\d{2}-\\\\d{2}$', in path [0, 'startDate']",
        ),
        (
            [
                {
                    "goal": "Lose weight",
                    "startDate": "2025-02-01",
                    "dueDate": "10-21-89",
                    "status": "improving",
                    "priority": "medium-priority",
                    "progressAndBarriers": "Motivated",
                }
            ],
            "'10-21-89' does not match '^\\\\d{4}-\\\\d{2}-\\\\d{2}$', in path [0, 'dueDate']",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Defined goal set by the provider, including due date and priority. "
        "There can be only one goal per instruction, and no instruction in the lack of."
    )
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
    tests = [
        ([], ""),
        (goals, 'Only document \'Goal\' for goals outside the following list: "display1a", "display2a", "display3a".'),
    ]
    for side_effect, expected in tests:
        current_goals.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        reset_mocks()


@patch.object(Goal, "can_edit_field", return_value=True)
def test_is_available(can_edit_field):
    tested = helper_instance()
    result = tested.is_available()
    assert result is True

    calls = [call("goal_statement"), call("progress")]
    assert can_edit_field.mock_calls == calls


@patch.object(Goal, "can_edit_field", return_value=False)
def test_is_available_all_fields_locked(can_edit_field):
    tested = helper_instance()
    result = tested.is_available()
    expected = False
    assert result == expected

    calls = [call("goal_statement"), call("progress")]
    assert can_edit_field.mock_calls == calls
