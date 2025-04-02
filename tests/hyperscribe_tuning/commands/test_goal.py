from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.goal import Goal
from hyperscribe_tuning.handlers.limited_cache import CodedItem


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
