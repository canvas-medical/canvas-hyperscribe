from datetime import date
from unittest.mock import patch, call

from canvas_sdk.commands.commands.follow_up import FollowUpCommand

from commander.protocols.commands.follow_up import FollowUp
from commander.protocols.commands.base import Base
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance(allow_update: bool = True) -> FollowUp:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=allow_update,
    )
    return FollowUp(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = FollowUp
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "followUp"
    assert result == expected


@patch.object(FollowUp, "existing_note_types")
def test_command_from_json(note_types):
    def reset_mocks():
        note_types.reset_mock()

    tested = helper_instance()
    items = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (-1, "theUuid1", [call()]),
        (0, "theUuid1", [call(), call()]),
        (1, "theUuid2", [call(), call()]),
        (2, "theUuid3", [call(), call()]),
        (3, "theUuid1", [call(), call()]),
    ]
    for idx, exp_uuid, calls in tests:
        note_types.side_effect = [items, items]
        parameters = {
            "visitType": "theVisit",
            "visitTypeIndex": idx,
            "date": "2025-02-04",
            "reasonForVisit": "theReasonForVisit",
            "comment": "theComment",
        }
        result = tested.command_from_json(parameters)
        expected = FollowUpCommand(
            note_uuid="noteUuid",
            structured=False,
            requested_date=date(2025, 2, 4),
            note_type_id=exp_uuid,
            reason_for_visit="theReasonForVisit",
            comment="theComment",
        )
        assert result == expected
        assert note_types.mock_calls == calls
        reset_mocks()


@patch.object(FollowUp, "existing_note_types")
def test_command_parameters(note_types):
    def reset_mocks():
        note_types.reset_mock()

    tested = helper_instance()

    note_types.side_effect = [[
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]]
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
    assert note_types.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Any follow up encounter, either virtually or in person."
                " There can be only one such instruction in the whole discussion, "
                "so if one was already found, just update it by intelligently merging all key information.")
    assert result == expected
    tested = helper_instance(False)
    result = tested.instruction_description()
    expected = "Any follow up encounter, either virtually or in person."
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    assert result == ""


@patch.object(FollowUp, "existing_note_types")
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
