from datetime import date
from unittest.mock import patch, call

from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.commands.base import Base
from commander.protocols.commands.surgery_history import SurgeryHistory
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.medical_concept import MedicalConcept
from commander.protocols.structures.settings import Settings


def helper_instance() -> SurgeryHistory:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return SurgeryHistory(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = SurgeryHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "surgicalHistory"
    assert result == expected


@patch.object(OpenaiChat, "single_conversation")
@patch.object(CanvasScience, "surgical_histories")
def test_command_from_json(surgical_histories, single_conversation):
    def reset_mocks():
        surgical_histories.reset_mock()
        single_conversation.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant surgery of a patient out of a list of surgeries.",
        "",
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the surgery of a patient:',
        '```text',
        'keywords: keyword1,keyword2,keyword3',
        ' -- ',
        'theComment',
        '```',
        'Among the following surgeries, identify the most relevant one:',
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
        "approximateDate": "2017-05-21",
        "comment": "theComment",
    }
    medications = [
        MedicalConcept(concept_id=123, term="termA"),
        MedicalConcept(concept_id=369, term="termB"),
        MedicalConcept(concept_id=752, term="termC"),
    ]

    # all good
    surgical_histories.side_effect = [medications]
    single_conversation.side_effect = [[{"concept_id": 369, "term": "termB"}]]

    result = tested.command_from_json(parameters)
    expected = PastSurgicalHistoryCommand(
        approximate_date=date(2017, 5, 21),
        past_surgical_history="termB",
        comment="theComment",
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert surgical_histories.mock_calls == calls
    calls = [call('openaiKey', system_prompt, user_prompt)]
    assert single_conversation.mock_calls == calls
    reset_mocks()

    # no good response
    surgical_histories.side_effect = [medications]
    single_conversation.side_effect = [[]]

    result = tested.command_from_json(parameters)
    expected = PastSurgicalHistoryCommand(
        approximate_date=date(2017, 5, 21),
        past_surgical_history=None,
        comment="theComment",
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert surgical_histories.mock_calls == calls
    calls = [call('openaiKey', system_prompt, user_prompt)]
    assert single_conversation.mock_calls == calls
    reset_mocks()

    # no medical concept
    surgical_histories.side_effect = [[]]
    single_conversation.side_effect = [[]]

    result = tested.command_from_json(parameters)
    expected = PastSurgicalHistoryCommand(
        approximate_date=date(2017, 5, 21),
        past_surgical_history=None,
        comment="theComment",
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert surgical_histories.mock_calls == calls
    assert single_conversation.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the surgery",
        "approximateDate": "YYYY-MM-DD",
        "comment": "description of the surgery, as free text",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Any past surgery. "
                "There can be only one surgery per instruction, and no instruction in the lack of.")
    assert result == expected


@patch.object(SurgeryHistory, "surgery_history")
def test_instruction_constraints(surgery_history):
    def reset_mocks():
        surgery_history.reset_mock()

    tested = helper_instance()
    surgeries = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        ([], ""),
        (surgeries, '"SurgeryHistory" cannot include: "display1a", "display2a", "display3a".'),
    ]
    for side_effect, expected in tests:
        surgery_history.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert surgery_history.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
