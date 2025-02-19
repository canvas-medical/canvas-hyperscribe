from commander.protocols.commands.base import Base
from commander.protocols.commands.physical_exam import PhysicalExam
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> PhysicalExam:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return PhysicalExam(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = PhysicalExam
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "exam"
    assert result == expected


def test_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    assert result is None


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
