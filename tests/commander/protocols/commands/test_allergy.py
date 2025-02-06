from datetime import date
from unittest.mock import patch, call

from canvas_sdk.commands.commands.allergy import AllergyCommand, Allergen, AllergenType

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.commands.allergy import Allergy
from commander.protocols.commands.base import Base
from commander.protocols.selector_chat import SelectorChat
from commander.protocols.structures.allergy_detail import AllergyDetail
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


@patch.object(SelectorChat, "single_conversation")
@patch.object(CanvasScience, "search_allergy")
def test_command_from_json(search_allergy, single_conversation):
    def reset_mocks():
        search_allergy.reset_mock()
        single_conversation.reset_mock()

    system_prompt = [
        'The conversation is in the medical context.',
        '',
        'Your task is to identify the most relevant allergy of a patient out of a list of allergies.',
        '',
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the allergy:',
        '```text',
        'keywords: keyword1,keyword2,keyword3',
        ' -- ',
        'severity: moderate',
        '',
        'theReaction',
        '```',
        '',
        'Among the following allergies, identify the most relevant one:',
        '',
        ' * descriptionA (conceptId: 134)\n * descriptionB (conceptId: 167)\n * descriptionC (conceptId: 234)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"conceptId": "the concept id, as int", "description": "the description"}]',
        '```',
        '',
    ]
    keywords = ['keyword1', 'keyword2', 'keyword3']
    tested = helper_instance()

    tests = [
        ('allergy group', 1, 1),
        ('medication', 2, 1),
        ('medication', 2, 2),
        ('ingredient', 6, 1),
        ('ingredient', 6, 6),
    ]
    for concept_type, exp_concept_id_type, selected_concept_id_type in tests:
        parameters = {
            'approximateDateOfOnset': '2025-02-04',
            'keywords': 'keyword1,keyword2,keyword3',
            'reaction': 'theReaction',
            'severity': 'moderate',
            'type': concept_type,
        }
        allergy_details = [
            AllergyDetail(
                concept_id_value=134,
                concept_id_description="descriptionA",
                concept_type="conceptTypeA",
                concept_id_type=1,
            ),
            AllergyDetail(
                concept_id_value=167,
                concept_id_description="descriptionB",
                concept_type="conceptTypeB",
                concept_id_type=selected_concept_id_type,
            ),
            AllergyDetail(
                concept_id_value=234,
                concept_id_description="descriptionC",
                concept_type="conceptTypeC",
                concept_id_type=exp_concept_id_type,
            ),
        ]
        # all good
        search_allergy.side_effect = [allergy_details]
        single_conversation.side_effect = [[{"conceptId": 167, "description": "descriptionB"}]]

        result = tested.command_from_json(parameters)
        expected = AllergyCommand(
            severity=AllergyCommand.Severity.MODERATE,
            narrative="theReaction",
            approximate_date=date(2025, 2, 4),
            allergy=Allergen(concept_id=167, concept_type=AllergenType(selected_concept_id_type)),
            note_uuid="noteUuid",
        )
        assert result == expected

        allergen_types = [AllergenType(1)]
        if exp_concept_id_type != 1:
            allergen_types.append(AllergenType(exp_concept_id_type))

        calls = [call('ontologiesHost', 'preSharedKey', keywords, allergen_types)]
        assert search_allergy.mock_calls == calls
        calls = [call(tested.settings, system_prompt, user_prompt)]
        assert single_conversation.mock_calls == calls
        reset_mocks()

        # no good response
        search_allergy.side_effect = [allergy_details]
        single_conversation.side_effect = [[]]

        result = tested.command_from_json(parameters)
        expected = AllergyCommand(
            severity=AllergyCommand.Severity.MODERATE,
            narrative="theReaction",
            approximate_date=date(2025, 2, 4),
            allergy=None,
            note_uuid="noteUuid",
        )
        assert result == expected

        allergen_types = [AllergenType(1)]
        if exp_concept_id_type != 1:
            allergen_types.append(AllergenType(exp_concept_id_type))

        calls = [call('ontologiesHost', 'preSharedKey', keywords, allergen_types)]
        assert search_allergy.mock_calls == calls
        calls = [call(tested.settings, system_prompt, user_prompt)]
        assert single_conversation.mock_calls == calls
        reset_mocks()

        # no allergies
        search_allergy.side_effect = [[]]
        single_conversation.side_effect = [[]]

        result = tested.command_from_json(parameters)
        expected = AllergyCommand(
            severity=AllergyCommand.Severity.MODERATE,
            narrative="theReaction",
            approximate_date=date(2025, 2, 4),
            allergy=None,
            note_uuid="noteUuid",
        )
        assert result == expected

        allergen_types = [AllergenType(1)]
        if exp_concept_id_type != 1:
            allergen_types.append(AllergenType(exp_concept_id_type))

        calls = [call('ontologiesHost', 'preSharedKey', keywords, allergen_types)]
        assert search_allergy.mock_calls == calls
        assert single_conversation.mock_calls == []
        reset_mocks()


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
        (allergies, "'Allergy' cannot include: display1a, display2a, display3a."),
        ([], ""),
    ]
    for side_effect, expected in tests:
        current_allergies.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_allergies.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
