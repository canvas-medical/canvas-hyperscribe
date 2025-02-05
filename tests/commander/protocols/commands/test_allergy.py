from unittest.mock import patch, call

from canvas_sdk.commands.commands.allergy import AllergyCommand

from commander.protocols.commands.allergy import Allergy
from commander.protocols.commands.base import Base
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.settings import Settings


def helper_instance() -> Allergy:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return Allergy(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = Allergy
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "allergy"
    assert result == expected


def te0st_command_from_json():
    tested = helper_instance()
    result = tested.command_from_json()
    expected = AllergyCommand()
    assert result == expected


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        'approximateDateOfOnset': 'YYYY-MM-DD',
        'keywords': 'comma separated keywords of up to 5 distinct synonyms of the component '
                    "related to the allergy or 'NKA' for No Known Allergy or 'NKDA' for No "
                    'Known Drug Allergy',
        'reaction': 'description of the reaction, as free text',
        'severity': 'mandatory, one of: mild/moderate/severe',
        'type': 'mandatory, one of: allergy group/medication/ingredient',
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Any diagnosed allergy, one instruction per allergy. "
                "There can be only one allergy per instruction, and no instruction in the lack of. "
                "But, if it is explicitly said that the patient has no known allergy, add an instruction mentioning it.")
    assert result == expected


@patch.object(Allergy, "current_allergies")
def test_instruction_constraints(current_allergies):
    def reset_mocks():
        current_allergies.reset_mock()

    tested = helper_instance()

    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (allergies, "'Allergy' cannot include: display1a, display2a, display3a.", [call(), call()]),
        ([], "", [call()]),
    ]
    for side_effect, expected, calls in tests:
        current_allergies.side_effect = [side_effect, side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        assert current_allergies.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
