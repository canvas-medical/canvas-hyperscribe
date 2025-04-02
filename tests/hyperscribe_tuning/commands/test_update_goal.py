from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.update_goal import UpdateGoal
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = UpdateGoal
    assert issubclass(tested, Base)


def test_schema_key():
    tested = UpdateGoal
    result = tested.schema_key()
    expected = "updateGoal"
    assert result == expected


def test_staged_command_extract():
    tested = UpdateGoal
    tests = [
        ({}, None),
        ({
             "due_date": "theDate",
             "priority": "thePriority",
             "progress": "theProgress",
             "goal_statement": {},
             "achievement_status": "theStatus"
         }, None),
        ({
             "due_date": "theDate",
             "priority": "thePriority",
             "progress": "theProgress",
             "goal_statement": {"text": "theGoal"},
             "achievement_status": "theStatus"
         }, CodedItem(label="theGoal: theProgress", code="", uuid="")),
        ({
             "due_date": "theDate",
             "priority": "thePriority",
             "progress": "",
             "goal_statement": {"text": "theGoal"},
             "achievement_status": "theStatus"
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
