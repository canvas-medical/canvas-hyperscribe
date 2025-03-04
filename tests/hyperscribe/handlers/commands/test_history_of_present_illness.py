from canvas_sdk.commands.commands.history_present_illness import HistoryOfPresentIllnessCommand

from hyperscribe.handlers.commands.base import Base
from hyperscribe.handlers.commands.history_of_present_illness import HistoryOfPresentIllness
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.structures.coded_item import CodedItem
from hyperscribe.handlers.structures.settings import Settings
from hyperscribe.handlers.structures.vendor_key import VendorKey


def helper_instance() -> HistoryOfPresentIllness:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return HistoryOfPresentIllness(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = HistoryOfPresentIllness
    assert issubclass(tested, Base)


def test_schema_key():
    tested = HistoryOfPresentIllness
    result = tested.schema_key()
    expected = "hpi"
    assert result == expected


def test_staged_command_extract():
    tested = HistoryOfPresentIllness
    tests = [
        ({}, None),
        ({"narrative": "theNarrative"}, CodedItem(label="theNarrative", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


def test_command_from_json():
    tested = helper_instance()
    parameters = {
        "narrative": "theNarrative",
    }
    result = tested.command_from_json(parameters)
    expected = HistoryOfPresentIllnessCommand(
        narrative="theNarrative",
        note_uuid="noteUuid",
    )
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "narrative": "highlights of the patient's symptoms and surrounding events and observations, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Highlights of the patient's symptoms and surrounding events and observations. "
                "There can be multiple highlights within an instruction, but only one such instruction in the whole discussion. "
                "So, if one was already found, simply update it by intelligently merging all key highlights.")
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
