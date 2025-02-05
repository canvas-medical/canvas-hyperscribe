from canvas_sdk.commands.commands.reason_for_visit import ReasonForVisitCommand
from commander.protocols.commands.reason_for_visit import ReasonForVisit

from commander.protocols.commands.base import Base
from commander.protocols.structures.settings import Settings

def helper_instance() -> ReasonForVisit:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return ReasonForVisit(settings, "patientUuid", "noteUuid", "providerUuid")

def test_class():
    tested = ReasonForVisit
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "reasonForVisit"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    expected = ReasonForVisitCommand()
    assert result == expected


def te0st_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {}
    assert result == expected


def te0st_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ""
    assert result == expected


def te0st_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = ""
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
