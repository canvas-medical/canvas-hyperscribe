from canvas_sdk.commands.commands.instruct import InstructCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.immunize import Immunize
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Immunize:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Immunize(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Immunize
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "immunize"
    assert result == expected


def test_command_from_json():
    tested = helper_instance()
    parameters = {
        "immunize": "theImmunization",
        "sig": "theSig",
    }
    result = tested.command_from_json(parameters)
    expected = InstructCommand(
        instruction="Advice to read information",
        comment='theSig - theImmunization',
        note_uuid="noteUuid",
    )
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "immunize": "medical name of the immunization and its CPT code",
        "sig": "directions, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Immunization or vaccine to be administered. "
                "There can be only one immunization per instruction, and no instruction in the lack of.")
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
