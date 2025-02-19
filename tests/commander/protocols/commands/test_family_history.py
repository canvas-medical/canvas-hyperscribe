from unittest.mock import patch, call

from canvas_sdk.commands.commands.family_history import FamilyHistoryCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.commands.base import Base
from commander.protocols.commands.family_history import FamilyHistory
from commander.protocols.helper import Helper
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.medical_concept import MedicalConcept
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> FamilyHistory:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
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


@patch.object(Helper, "chatter")
@patch.object(CanvasScience, "family_histories")
def test_command_from_json(family_histories, chatter):
    def reset_mocks():
        family_histories.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant condition of a patient out of a list of conditions.",
        "",
    ]
    user_prompt = [
        'Here is the note provided by the healthcare provider in regards to the condition of a patient:',
        '```text',
        'keywords: keyword1,keyword2,keyword3',
        ' -- ',
        'theNote',
        '```',
        'Among the following conditions, identify the most relevant one:',
        '',
        ' * termA (123)\n * termB (369)\n * termC (752)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json', '[{"concept_id": "the concept ID", "term": "the expression"}]',
        '```',
        '',
    ]
    keywords = ['keyword1', 'keyword2', 'keyword3']
    tested = helper_instance()

    parameters = {
        'keywords': 'keyword1,keyword2,keyword3',
        'relative': 'sibling',
        'note': 'theNote',
    }
    medical_concepts = [
        MedicalConcept(concept_id=123, term="termA"),
        MedicalConcept(concept_id=369, term="termB"),
        MedicalConcept(concept_id=752, term="termC"),
    ]

    # all good
    family_histories.side_effect = [medical_concepts]
    chatter.return_value.single_conversation.side_effect = [[{"conceptId": 369, "term": "termB"}]]

    result = tested.command_from_json(parameters)
    expected = FamilyHistoryCommand(
        relative="sibling",
        note="theNote",
        family_history="termB",
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert family_histories.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    family_histories.side_effect = [medical_concepts]
    chatter.return_value.single_conversation.side_effect = [[]]

    result = tested.command_from_json(parameters)
    expected = FamilyHistoryCommand(
        relative="sibling",
        note="theNote",
        family_history=None,
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert family_histories.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    family_histories.side_effect = [[]]
    chatter.return_value.single_conversation.side_effect = [[]]

    result = tested.command_from_json(parameters)
    expected = FamilyHistoryCommand(
        relative="sibling",
        note="theNote",
        family_history=None,
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert family_histories.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


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
