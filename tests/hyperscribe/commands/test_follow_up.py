from datetime import date
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.follow_up import FollowUpCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.follow_up import FollowUp
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance(structured_rfv: bool = False) -> FollowUp:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=structured_rfv,
        audit_llm=False,
    )
    cache = LimitedCache("patientUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return FollowUp(settings, cache, identification)


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


@patch.object(LimitedCache, "existing_reason_for_visits")
@patch.object(LimitedCache, "existing_note_types")
def test_command_from_json(existing_note_types, existing_reason_for_visits):
    chatter = MagicMock()

    def reset_mocks():
        existing_note_types.reset_mock()
        existing_reason_for_visits.reset_mock()

    visit_types = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    reason_for_visits = [
        CodedItem(uuid="theUuidX", label="displayX", code="codeX"),
        CodedItem(uuid="theUuidY", label="displayY", code="codeY"),
        CodedItem(uuid="theUuidZ", label="displayZ", code="codeZ"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    tests = [
        (-1, "theUuid1", [call()]),
        (0, "theUuid1", [call(), call()]),
        (1, "theUuid2", [call(), call()]),
        (2, "theUuid3", [call(), call()]),
        (3, "theUuid1", [call(), call()]),
    ]
    for idx, exp_uuid, calls in tests:
        existing_note_types.side_effect = [visit_types, visit_types]
        existing_reason_for_visits.side_effect = []
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "visitType": "theVisit",
                "visitTypeIndex": idx,
                "date": "2025-02-04",
                "reasonForVisit": "theReasonForVisit",
                "comment": "theComment",
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = FollowUpCommand(
            note_uuid="noteUuid",
            structured=False,
            requested_date=date(2025, 2, 4),
            note_type_id=exp_uuid,
            reason_for_visit="theReasonForVisit",
            comment="theComment",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        assert existing_note_types.mock_calls == calls
        assert existing_reason_for_visits.mock_calls == []
        assert chatter.mock_calls == []
        reset_mocks()

    # with structured RfV
    tested = helper_instance(structured_rfv=True)
    tests = [
        (1, "theUuidY", True),
        (2, "theUuidZ", True),
        (4, None, False),
    ]
    for idx, exp_uuid, exp_structured in tests:
        existing_note_types.side_effect = [visit_types, visit_types]
        existing_reason_for_visits.side_effect = [reason_for_visits]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "visitType": "theVisit",
                "visitTypeIndex": 2,
                "date": "2025-02-04",
                "reasonForVisit": "theReasonForVisit",
                "reasonForVisitIndex": idx,
                "comment": "theComment",
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = FollowUpCommand(
            note_uuid="noteUuid",
            structured=exp_structured,
            requested_date=date(2025, 2, 4),
            note_type_id="theUuid3",
            reason_for_visit="theReasonForVisit",
            comment="theComment",
        )
        if exp_uuid:
            command.reason_for_visit = exp_uuid
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        calls = [call(), call()]
        assert existing_note_types.mock_calls == calls
        calls = [call()]
        assert existing_reason_for_visits.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
@patch.object(LimitedCache, "existing_note_types")
def test_command_parameters(existing_note_types, existing_reason_for_visits):
    def reset_mocks():
        existing_note_types.reset_mock()

    visit_types = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    reason_for_visits = [
        CodedItem(uuid="theUuidX", label="displayX", code="codeX"),
        CodedItem(uuid="theUuidY", label="displayY", code="codeY"),
        CodedItem(uuid="theUuidZ", label="displayZ", code="codeZ"),
    ]

    # no structured RfV
    tested = helper_instance(structured_rfv=False)
    existing_note_types.side_effect = [visit_types]
    existing_reason_for_visits.side_effect = []
    result = tested.command_parameters()
    expected = {
        "visitType": "one of: display1a (index:0)/display2a (index:1)/display3a (index:2)",
        "visitTypeIndex": "index of the visitType, as integer",
        "date": "date of the follow up encounter, as YYYY-MM-DD",
        "reasonForVisit": "the main reason for the follow up encounter, as free text",
        "comment": "information related to the scheduling itself, as free text",
    }
    assert result == expected
    calls = [call()]
    assert existing_note_types.mock_calls == calls
    assert existing_reason_for_visits.mock_calls == []
    reset_mocks()

    # no structured RfV
    tested = helper_instance(structured_rfv=True)
    existing_note_types.side_effect = [visit_types]
    existing_reason_for_visits.side_effect = [reason_for_visits]
    result = tested.command_parameters()
    expected = {
        "visitType": "one of: display1a (index:0)/display2a (index:1)/display3a (index:2)",
        "visitTypeIndex": "index of the visitType, as integer",
        "date": "date of the follow up encounter, as YYYY-MM-DD",
        "reasonForVisit": "one of: displayX/displayY/displayZ",
        "reasonForVisitIndex": "the index of the reason for visit, as integer",
        "comment": "information related to the scheduling itself, as free text",
    }
    assert result == expected
    calls = [call()]
    assert existing_note_types.mock_calls == calls
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Any follow up encounter, either virtually or in person."
                " There can be only one such instruction in the whole discussion, "
                "so if one was already found, just update it by intelligently merging all key information.")
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    assert result == ""


@patch.object(LimitedCache, "existing_note_types")
def test_is_available(note_types):
    def reset_mocks():
        note_types.reset_mock()

    tested = helper_instance()
    #
    note_types.side_effect = [[]]
    result = tested.is_available()
    assert result is False
    calls = [call()]
    assert note_types.mock_calls == calls
    reset_mocks()
    #
    note_types.side_effect = [[
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]]
    result = tested.is_available()
    assert result is True
    calls = [call()]
    assert note_types.mock_calls == calls
    reset_mocks()
