from unittest.mock import MagicMock

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.commands.physical_exam import PhysicalExam
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe.handlers.structures.settings import Settings
from hyperscribe.handlers.structures.vendor_key import VendorKey


def helper_instance() -> PhysicalExam:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return PhysicalExam(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = PhysicalExam
    assert issubclass(tested, Base)


def test_schema_key():
    tested = PhysicalExam
    result = tested.schema_key()
    expected = "exam"
    assert result == expected


def test_staged_command_extract():
    tested = PhysicalExam
    tests = [
        ({}, None),
        ({
             "question-1": "theQuestion1",
             "question-2": "theQuestion2",
             "question-3": "theQuestion3",
             "questionnaire": {
                 "text": "theQuestionnaire",
                 "extra": {
                     "questions": [
                         {"name": "question-1"},
                         {"name": "question-2"},
                         {"name": "question-3"},
                     ],
                 },
             }
         }, CodedItem(label="theQuestionnaire: theQuestion1 \n theQuestion2 \n theQuestion3", code="", uuid="")),
        ({
             "question-1": "theQuestion1",
             "question-2": "theQuestion2",
             "question-3": "theQuestion3",
             "questionnaire": {
                 "text": "",
                 "extra": {
                     "questions": [
                         {"name": "question-1"},
                         {"name": "question-2"},
                         {"name": "question-3"},
                     ],
                 },
             }
         }, None),
        ({
             "question-1": "theQuestion1",
             "question-4": "theQuestion4",
             "question-3": "theQuestion3",
             "questionnaire": {
                 "text": "theQuestionnaire",
                 "extra": {
                     "questions": [
                         {"name": "question-1"},
                         {"name": "question-2"},
                         {"name": "question-3"},
                     ],
                 },
             }
         }, CodedItem(label="theQuestionnaire: theQuestion1 \n theQuestion3", code="", uuid="")),
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
    result = tested.command_from_json(chatter, {})
    assert result is None
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {}
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ""
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is False
