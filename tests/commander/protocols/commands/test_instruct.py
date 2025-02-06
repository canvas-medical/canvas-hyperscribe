from canvas_sdk.commands.commands.instruct import InstructCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.instruct import Instruct
from commander.protocols.structures.settings import Settings


def helper_instance() -> Instruct:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Instruct(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Instruct
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "instruct"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    expected = InstructCommand()
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated single keywords of up to 5 synonyms to the specific direction",
        "comment": "directions from the provider, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Specific or standard direction. "
                "There can be only one direction per instruction, and no instruction in the lack of.")
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
