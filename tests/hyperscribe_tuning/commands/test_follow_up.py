from hyperscribe_tuning.commands.base import Base
from hyperscribe_tuning.commands.follow_up import FollowUp
from hyperscribe_tuning.handlers.limited_cache import CodedItem


def test_class():
    tested = FollowUp
    assert issubclass(tested, Base)


def test_schema_key():
    tested = FollowUp
    result = tested.schema_key()
    expected = "followUp"
    assert result == expected


def test_staged_command_extract():
    tested = FollowUp
    tests = [
        ({}, None),
        ({
             "coding": {"text": "theStructuredRfV"},
             "comment": "theComment",
             "note_type": {"text": "theNoteType"},
             "requested_date": {"date": "theDate"},
             "reason_for_visit": "theReasonForVisit"
         }, CodedItem(label="theDate: theStructuredRfV (theNoteType)", code="", uuid="")),
        ({
             "coding": {"text": "theStructuredRfV"},
             "comment": "theComment",
             "note_type": {"text": "theNoteType"},
             "requested_date": {"date": ""},
             "reason_for_visit": "theReasonForVisit"
         }, None),
        ({
             "coding": {"text": ""},
             "comment": "theComment",
             "note_type": {"text": "theNoteType"},
             "requested_date": {"date": "theDate"},
             "reason_for_visit": "theReasonForVisit"
         }, CodedItem(label="theDate: theReasonForVisit (theNoteType)", code="", uuid="")),
        ({
             "coding": {"text": ""},
             "comment": "theComment",
             "note_type": {"text": "theNoteType"},
             "requested_date": {"date": "theDate"},
             "reason_for_visit": ""
         }, None),
        ({
             "coding": {"text": ""},
             "comment": "theComment",
             "note_type": {"text": "theNoteType"},
             "requested_date": {"date": ""},
             "reason_for_visit": "theReasonForVisit"
         }, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected
