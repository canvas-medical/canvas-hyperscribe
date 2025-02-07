from datetime import datetime
from unittest.mock import patch, call

from canvas_sdk.commands.commands.update_goal import UpdateGoalCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.update_goal import UpdateGoal
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> UpdateGoal:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return UpdateGoal(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = UpdateGoal
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "updateGoal"
    assert result == expected


@patch.object(UpdateGoal, "current_goals")
def test_command_from_json(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="123"),
        CodedItem(uuid="theUuid2", label="display2a", code="45"),
        CodedItem(uuid="theUuid3", label="display3a", code="9876"),

    ]
    tests = [
        (1, "theUuid2"),
        (2, "theUuid3"),
        (4, ""),
    ]
    for idx, exp_uuid in tests:
        current_goals.side_effect = [goals, goals]
        params = {
            'goal': 'display2a',
            'goalIndex': idx,
            "dueDate": "2025-02-03",
            'status': 'improving',
            'priority': 'medium-priority',
            'progressAndBarriers': 'theProgressAndBarriers',
        }
        result = tested.command_from_json(params)
        expected = UpdateGoalCommand(
            goal_id=exp_uuid,
            due_date=datetime(2025, 2, 3),
            priority=UpdateGoalCommand.Priority.MEDIUM,
            achievement_status=UpdateGoalCommand.AchievementStatus.IMPROVING,
            progress="theProgressAndBarriers",
            note_uuid="noteUuid",
        )
        assert result == expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        reset_mocks()


@patch.object(UpdateGoal, "current_goals")
def test_command_parameters(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    current_goals.side_effect = [goals]
    result = tested.command_parameters()
    expected = {
        'goal': 'one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)',
        'goalIndex': 'index of the Goal to update, as integer',
        "dueDate": "YYYY-MM-DD",
        "status": "one of: in-progress/improving/worsening/no-change/achieved/sustaining/not-achieved/no-progress/not-attainable",
        "priority": "one of: high-priority/medium-priority/low-priority",
        'progressAndBarriers': 'progress or barriers, as free text',
    }
    assert result == expected
    calls = [call()]
    assert current_goals.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = "Change of status of a previously set goal, including progress, barriers, priority or due date."
    assert result == expected


@patch.object(UpdateGoal, "current_goals")
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


@patch.object(UpdateGoal, "current_goals")
def test_is_available(current_goals):
    def reset_mocks():
        current_goals.reset_mock()

    tested = helper_instance()
    goals = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (goals, True),
        ([], False),
    ]
    for side_effect, expected in tests:
        current_goals.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        reset_mocks()
