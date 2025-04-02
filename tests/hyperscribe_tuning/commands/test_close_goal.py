from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.close_goal import CloseGoal
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = CloseGoal
    assert issubclass(tested, Base)


def test_schema_key():
    tested = CloseGoal
    result = tested.schema_key()
    expected = "closeGoal"
    assert result == expected


def test_staged_command_extract():
    tested = CloseGoal
    tests = [
        ({}, None),
        ({
             "goal_id": {},
             "progress": "the Progress",
             "achievement_status": "in-progress"
         }, None),
        ({
             "goal_id": {"text": "theGoal"},
             "progress": "theProgress",
             "achievement_status": "in-progress"
         }, CodedItem(label="theGoal (theProgress)", code="", uuid="")),
        ({
             "goal_id": {"text": "theGoal"},
             "progress": "",
             "achievement_status": "in-progress"
         }, CodedItem(label="theGoal (n/a)", code="", uuid="")),

    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
