from unittest.mock import patch, call

from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.reason_for_visit import ReasonForVisit
from commander.protocols.limited_cache import LimitedCache
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> ReasonForVisit:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
    )
    cache = LimitedCache("patientUuid")
    return ReasonForVisit(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = ReasonForVisit
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "reasonForVisit"
    assert result == expected


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_command_from_json(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    tested = helper_instance()

    # no structured RfV
    parameters = {
        "reasonForVisit": "theReasonForVisit",
    }
    result = tested.command_from_json(parameters)
    expected = ReasonForVisitCommand(
        comment="theReasonForVisit",
        note_uuid="noteUuid",
    )
    assert result == expected
    assert existing_reason_for_visits.mock_calls == []
    reset_mocks()

    # with structured RfV
    tests = [
        (1, "theUuid2", True),
        (2, "theUuid3", True),
        (4, None, False),
    ]
    for idx, exp_uuid, exp_structured in tests:
        existing_reason_for_visits.side_effect = [reason_for_visits]
        parameters = {
            "reasonForVisit": "theReasonForVisit",
            "presetReasonForVisit": "display2a",
            "presetReasonForVisitIndex": idx,
        }
        result = tested.command_from_json(parameters)
        expected = ReasonForVisitCommand(
            comment="theReasonForVisit",
            note_uuid="noteUuid",
        )
        if exp_structured:
            expected.structured = exp_structured
        if exp_uuid:
            expected.coding = exp_uuid
        assert result == expected
        calls = [call()]
        assert existing_reason_for_visits.mock_calls == calls
        reset_mocks()


@patch.object(LimitedCache, "existing_reason_for_visits")
def test_command_parameters(existing_reason_for_visits):
    def reset_mocks():
        existing_reason_for_visits.reset_mock()

    reason_for_visits = [
        CodedItem(uuid="theUuid1", label="display1", code="code1"),
        CodedItem(uuid="theUuid2", label="display2", code="code2"),
        CodedItem(uuid="theUuid3", label="display3", code="code3"),
    ]

    tested = helper_instance()

    # no structured RfV
    existing_reason_for_visits.side_effect = [[]]
    result = tested.command_parameters()
    expected = {
        "reasonForVisit": "extremely concise description of the reason or impetus for the visit, as free text",
    }
    assert result == expected
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()

    # with structured RfV
    existing_reason_for_visits.side_effect = [reason_for_visits]
    result = tested.command_parameters()
    expected = {
        "reasonForVisit": "extremely concise description of the reason or impetus for the visit, as free text",
        "presetReasonForVisit": "None or, the one of the following that fully encompasses the reason for visit: display1/display2/display3",
        "presetReasonForVisitIndex": "the index of the preset reason for visit or -1, as integer",
    }
    assert result == expected
    calls = [call()]
    assert existing_reason_for_visits.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Patient's reported reason or impetus for the visit, extremely concise. "
                "There can be multiple reasons within an instruction, "
                "but only one such instruction in the whole discussion. "
                "So, if one was already found, simply update it by intelligently merging all reasons.")
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
