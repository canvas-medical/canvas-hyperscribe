from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.task import Task
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Task
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Task
    result = tested.schema_key()
    expected = "task"
    assert result == expected


def test_staged_command_extract():
    tested = Task
    tests = [
        ({}, None),
        ({
             "title": "theTask",
             "labels": [
                 {"text": "label1"},
                 {"text": "label2"},
                 {"text": "label3"},
             ],
             "comment": "theComment",
             "due_date": "theDate",
         }, CodedItem(label="theTask: theComment (due on: theDate, labels: label1/label2/label3)", code="", uuid="")),
        ({
             "title": "",
             "labels": [
                 {"text": "label1"},
                 {"text": "label2"},
                 {"text": "label3"},
             ],
             "comment": "theComment",
             "due_date": "theDate",
         }, None),
        ({
             "title": "theTask",
             "labels": [],
             "comment": "theComment",
             "due_date": "theDate",
         }, CodedItem(label="theTask: theComment (due on: theDate, labels: n/a)", code="", uuid="")),
        ({
             "title": "theTask",
             "labels": [{"text": "label1"}],
             "comment": "",
             "due_date": "",
         }, CodedItem(label="theTask: n/a (due on: n/a, labels: label1)", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
