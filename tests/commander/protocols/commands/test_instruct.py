from unittest.mock import patch, call

from canvas_sdk.commands.commands.instruct import InstructCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.commands.base import Base
from commander.protocols.commands.instruct import Instruct
from commander.protocols.helper import Helper
from commander.protocols.structures.medical_concept import MedicalConcept
from commander.protocols.structures.settings import Settings
from commander.protocols.structures.vendor_key import VendorKey


def helper_instance() -> Instruct:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
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


@patch.object(Helper, "chatter")
@patch.object(CanvasScience, "instructions")
def test_command_from_json(instructions, chatter):
    def reset_mocks():
        instructions.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant direction.",
        "",
    ]
    user_prompt = [
        'Here is the description of a direction instructed by a healthcare provider to a patient:',
        '```text',
        'keywords: keyword1,keyword2,keyword3',
        ' -- ',
        'theComment',
        '```',
        'Among the following expressions, identify the most relevant one:',
        '',
        ' * termA (123)\n * termB (369)\n * termC (752)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"concept_id": "the concept ID", "term": "the expression"}]',
        '```',
        '',
    ]
    keywords = ['keyword1', 'keyword2', 'keyword3']
    tested = helper_instance()

    parameters = {
        'keywords': 'keyword1,keyword2,keyword3',
        'comment': 'theComment',
    }
    medical_concepts = [
        MedicalConcept(concept_id=123, term="termA"),
        MedicalConcept(concept_id=369, term="termB"),
        MedicalConcept(concept_id=752, term="termC"),
    ]

    # all good
    instructions.side_effect = [medical_concepts]
    chatter.return_value.single_conversation.side_effect = [[{"conceptId": 369, "term": "termB"}]]

    result = tested.command_from_json(parameters)
    expected = InstructCommand(
        instruction="termB",
        comment="theComment",
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert instructions.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    instructions.side_effect = [medical_concepts]
    chatter.return_value.single_conversation.side_effect = [[]]

    result = tested.command_from_json(parameters)
    expected = InstructCommand(
        instruction="Advice to read information",
        comment="theComment",
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert instructions.mock_calls == calls
    calls = [
        call(tested.settings),
        call().single_conversation(system_prompt, user_prompt),
    ]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    instructions.side_effect = [[]]
    chatter.return_value.single_conversation.side_effect = [[]]

    result = tested.command_from_json(parameters)
    expected = InstructCommand(
        instruction="Advice to read information",
        comment="theComment",
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert instructions.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


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
