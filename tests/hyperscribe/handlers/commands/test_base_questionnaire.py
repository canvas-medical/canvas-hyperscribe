from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.handlers.structures.coded_item import CodedItem


def test_class():
    tested = BaseQuestionnaire
    assert issubclass(tested, Base)


def test_staged_command_extract():
    tested = BaseQuestionnaire
    tests = [
        ({}, None),
        ({
             "questionnaire": {
                 "text": "theQuestionnaire",
                 "extra": {
                     "questions": [
                         {"label": "theQuestion1"},
                         {"label": "theQuestion2"},
                         {"label": "theQuestion3"},
                     ],
                 },
             }
         }, CodedItem(label="theQuestionnaire: theQuestion1 \n theQuestion2 \n theQuestion3", code="", uuid="")),
        ({
             "questionnaire": {
                 "text": "",
                 "extra": {
                     "questions": [
                         {"label": "theQuestion1"},
                         {"label": "theQuestion2"},
                         {"label": "theQuestion3"},
                     ],
                 },
             }
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
