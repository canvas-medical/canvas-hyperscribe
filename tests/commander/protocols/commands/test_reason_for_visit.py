from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.reason_for_visit import ReasonForVisit
from commander.protocols.limited_cache import LimitedCache
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


def test_command_from_json():
    tested = helper_instance()
    parameters = {
        "reasonForVisit": "theReasonForVisit",
    }
    result = tested.command_from_json(parameters)
    expected = ReasonForVisitCommand(
        comment="theReasonForVisit",
        note_uuid="noteUuid",
    )
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "reasonForVisit": "description of the reason of the visit, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Patient's reported reason for the visit. "
                "There can be multiple reasons within an instruction."
                " There can be only one such instruction in the whole discussion, "
                "so if one was already found, just update it by intelligently merging all reasons.")
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
