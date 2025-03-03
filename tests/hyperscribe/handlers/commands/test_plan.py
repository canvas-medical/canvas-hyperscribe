from canvas_sdk.commands.commands.plan import PlanCommand

from hyperscribe.protocols.commands.base import Base
from hyperscribe.protocols.commands.plan import Plan
from hyperscribe.protocols.limited_cache import LimitedCache
from hyperscribe.protocols.structures.coded_item import CodedItem
from hyperscribe.protocols.structures.settings import Settings
from hyperscribe.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Plan:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
    )
    cache = LimitedCache("patientUuid", {})
    return Plan(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Plan
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Plan
    result = tested.schema_key()
    expected = "plan"
    assert result == expected


def test_staged_command_extract():
    tested = Plan
    tests = [
        ({}, None),
        ({"narrative": "theNarrative"}, CodedItem(label="theNarrative", code="", uuid="")),
        ({"narrative": ""}, None),
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
        "plan": "thePlan",
    }
    result = tested.command_from_json(parameters)
    expected = PlanCommand(
        narrative="thePlan",
        note_uuid="noteUuid",
    )
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "plan": "description of the plan, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Defined plan for future patient visits. "
                "There can be only one plan per instruction, and no instruction in the lack of.")
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
