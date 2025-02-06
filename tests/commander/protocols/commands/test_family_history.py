from unittest.mock import patch, call

from canvas_sdk.commands.commands.family_history import FamilyHistoryCommand

from commander.protocols.commands.base import Base
from commander.protocols.commands.family_history import FamilyHistory
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> FamilyHistory:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return FamilyHistory(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = FamilyHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "familyHistory"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json({})
    expected = FamilyHistoryCommand()
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the condition",
        "relative": "one of: father/mother/parent/child/brother/sister/sibling/grand-parent/grand-father/grand-mother",
        "note": "description of the condition, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Any relevant condition of a relative among: "
                "father, mother, parent, child, brother, sister, sibling, grand-parent, grand-father, grand-mother. "
                "There can be only one condition per relative per instruction, and no instruction in the lack of.")
    assert result == expected


@patch.object(FamilyHistory, "family_history")
def test_instruction_constraints(family_history):
    def reset_mocks():
        family_history.reset_mock()

    tested = helper_instance()

    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (allergies, '"FamilyHistory" cannot include: display1a, display2a, display3a.'),
        ([], ""),
    ]
    for side_effect, expected in tests:
        family_history.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert family_history.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
