from datetime import date
from unittest.mock import patch, call

from canvas_sdk.commands.commands.medical_history import MedicalHistoryCommand

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.commands.base import Base
from commander.protocols.commands.medical_history import MedicalHistory
from commander.protocols.selector_chat import SelectorChat
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.icd10_condition import Icd10Condition
from commander.protocols.structures.settings import Settings


def helper_instance() -> MedicalHistory:
    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    return MedicalHistory(settings, "patientUuid", "noteUuid", "providerUuid")


def test_class():
    tested = MedicalHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = helper_instance()
    result = tested.schema_key()
    expected = "medicalHistory"
    assert result == expected


@patch.object(SelectorChat, "single_conversation")
@patch.object(CanvasScience, "medical_histories")
def test_command_from_json(medical_histories, single_conversation):
    def reset_mocks():
        medical_histories.reset_mock()
        single_conversation.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant condition of a patient out of a list of conditions.",
        "",
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the condition of a patient:',
        '```text',
        'keywords: keyword1,keyword2,keyword3',
        ' -- ',
        'theComment',
        '```',
        'Among the following conditions, identify the most relevant one:',
        '',
        ' * labelA (ICD10: code123)\n * labelB (ICD10: code369)\n * labelC (ICD10: code752)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"icd10": "the concept ID", "label": "the expression"}]',
        '```',
        '',
    ]
    keywords = ['keyword1', 'keyword2', 'keyword3']
    tested = helper_instance()

    parameters = {
        'keywords': 'keyword1,keyword2,keyword3',
        "approximateStartDate": "2018-03-15",
        "approximateEndDate": "2021-07-19",
        'comments': 'theComment',
    }
    conditions = [
        Icd10Condition(code="code123", label="labelA"),
        Icd10Condition(code="code369", label="labelB"),
        Icd10Condition(code="code752", label="labelC"),
    ]

    # all good
    medical_histories.side_effect = [conditions]
    single_conversation.side_effect = [[{"icd10": "code369", "label": "labelB"}]]

    result = tested.command_from_json(parameters)
    expected = MedicalHistoryCommand(
        approximate_start_date=date(2018, 3, 15),
        approximate_end_date=date(2021, 7, 19),
        show_on_condition_list=True,
        comments="theComment",
        past_medical_history="labelB",
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medical_histories.mock_calls == calls
    calls = [call(tested.settings, system_prompt, user_prompt)]
    assert single_conversation.mock_calls == calls
    reset_mocks()

    # no good response
    medical_histories.side_effect = [conditions]
    single_conversation.side_effect = [[]]

    result = tested.command_from_json(parameters)
    expected = MedicalHistoryCommand(
        approximate_start_date=date(2018, 3, 15),
        approximate_end_date=date(2021, 7, 19),
        show_on_condition_list=True,
        comments="theComment",
        past_medical_history=None,
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medical_histories.mock_calls == calls
    calls = [call(tested.settings, system_prompt, user_prompt)]
    assert single_conversation.mock_calls == calls
    reset_mocks()

    # no medical concept
    medical_histories.side_effect = [[]]
    single_conversation.side_effect = [[]]

    result = tested.command_from_json(parameters)
    expected = MedicalHistoryCommand(
        approximate_start_date=date(2018, 3, 15),
        approximate_end_date=date(2021, 7, 19),
        show_on_condition_list=True,
        comments="theComment",
        past_medical_history=None,
        note_uuid="noteUuid",
    )
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medical_histories.mock_calls == calls
    assert single_conversation.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "comma separated keywords of up to 5 synonyms of the condition",
        "approximateStartDate": "YYYY-MM-DD",
        "approximateEndDate": "YYYY-MM-DD",
        "comments": "provided description of the patient specific history with the condition, as free text",
    }

    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = ("Any past condition. "
                "There can be only one condition per instruction, and no instruction in the lack of.")
    assert result == expected


@patch.object(MedicalHistory, "condition_history")
def test_instruction_constraints(condition_history):
    def reset_mocks():
        condition_history.reset_mock()

    tested = helper_instance()

    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (conditions, "'MedicalHistory' cannot include: display1a, display2a, display3a."),
        ([], ""),
    ]
    for side_effect, expected in tests:
        condition_history.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert condition_history.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
