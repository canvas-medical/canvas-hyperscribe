from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.refer import Refer
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = Refer
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Refer
    result = tested.schema_key()
    expected = "refer"
    assert result == expected


def test_staged_command_extract():
    tested = Refer
    tests = [
        ({}, None),
        ({
             "priority": "Urgent",
             "refer_to": {"text": "theReferred"},
             "indications": [
                 {"text": "Indication1"},
                 {"text": "Indication2"},
                 {"text": "Indication3"},
             ],
             "internal_comment": "theComment",
             "clinical_question": "theClinicalQuestion",
             "notes_to_specialist": "theNote",
             "documents_to_include": [
                 {"text": "Document1"},
                 {"text": "Document2"},
                 {"text": "Document3"},
             ]
         }, CodedItem(
            label="referred to theReferred: theNote "
                  "(priority: Urgent, question: theClinicalQuestion, "
                  "documents: Document1/Document2/Document3, "
                  "related conditions: Indication1/Indication2/Indication3)",
            code="",
            uuid="",
        )),
        ({
             "refer_to": {"text": "theReferred"},
         }, CodedItem(
            label="referred to theReferred: n/a (priority: n/a, question: n/a, documents: n/a, related conditions: n/a)",
            code="",
            uuid="",
        )),
        ({
             "priority": "Urgent",
             "refer_to": {"text": ""},
             "indications": [
                 {"text": "Indication1"},
                 {"text": "Indication2"},
                 {"text": "Indication3"},
             ],
             "internal_comment": "theComment",
             "clinical_question": "theClinicalQuestion",
             "notes_to_specialist": "theNote",
             "documents_to_include": [
                 {"text": "Document1"},
                 {"text": "Document2"},
                 {"text": "Document3"},
             ]
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
