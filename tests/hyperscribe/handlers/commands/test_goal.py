from datetime import datetime
from unittest.mock import patch, call

from canvas_sdk.commands.commands.goal import GoalCommand

from hyperscribe.protocols.commands.base import Base
from hyperscribe.protocols.commands.goal import Goal
from hyperscribe.protocols.limited_cache import LimitedCache
from hyperscribe.protocols.structures.coded_item import CodedItem
from hyperscribe.protocols.structures.settings import Settings
from hyperscribe.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Goal:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return Goal(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Goal
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Goal
    result = tested.schema_key()
    expected = "goal"
    assert result == expected


def test_staged_command_extract():
    tested = Goal
    tests = [
        ({}, None),
        ({
             "due_date": "2025-02-27",
             "priority": "medium-priority",
             "progress": "theProgress",
             "start_date": "2025-02-26",
             "goal_statement": "theGoal",
             "achievement_status": "improving"
         }, CodedItem(label="theGoal", code="", uuid="")),
        ({
             "due_date": "2025-02-27",
             "priority": "medium-priority",
             "progress": "theProgress",
             "start_date": "2025-02-26",
             "goal_statement": "",
             "achievement_status": "improving"
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


def test_command_from_json():
    tested = helper_instance()
    parameters = {
        "goal": "theGoal",
        "startDate": "2023-11-12",
        "dueDate": "2025-02-04",
        "status": "improving",
        "priority": "medium-priority",
        "progressAndBarriers": "theProgressAndBarriers",
    }
    result = tested.command_from_json(parameters)
    expected = GoalCommand(
        goal_statement="theGoal",
        start_date=datetime(2023, 11, 12),
        due_date=datetime(2025, 2, 4),
        achievement_status=GoalCommand.AchievementStatus.IMPROVING,
        priority=GoalCommand.Priority.MEDIUM,
        progress="theProgressAndBarriers",
        note_uuid="noteUuid",
    )
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "goal": "title of the goal, as free text",
        "startDate": "YYYY-MM-DD",
        "dueDate": "YYYY-MM-DD",
        "status": "one of: in-progress/improving/worsening/no-change/achieved/sustaining/not-achieved/no-progress/not-attainable",
        "priority": "one of: high-priority/medium-priority/low-priority",
        "progressAndBarriers": "progress and barriers, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Defined goal set by the provider, including due date and priority. "
                "There can be only one goal per instruction, and no instruction in the lack of.")
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
        (goals, '"Goal" cannot include: "display1a", "display2a", "display3a"'),
    ]
    for side_effect, expected in tests:
        current_goals.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_goals.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
