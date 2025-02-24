from canvas_sdk.commands.commands.plan import PlanCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.plan import Plan
from commander.protocols.limited_cache import LimitedCache
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Plan:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
    )
    cache = LimitedCache("patientUuid")
    return Plan(settings, cache, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Plan
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "plan"
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
