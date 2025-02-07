from unittest.mock import patch, call, MagicMock

from django.db.models import Q

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.selector_chat import SelectorChat
from commander.protocols.structures.coded_item import CodedItem
from commander.protocols.structures.icd10_condition import Icd10Condition
from commander.protocols.structures.json_extract import JsonExtract
from commander.protocols.structures.settings import Settings
from commander.protocols.temporary_data import DataLabTestView


@patch.object(SelectorChat, "single_conversation")
@patch.object(CanvasScience, "search_conditions")
def test_condition_from(search_conditions, single_conversation):
    def reset_mocks():
        search_conditions.reset_mock()
        single_conversation.reset_mock()

    tested = SelectorChat

    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant condition diagnosed for a patient out of a list of conditions.",
        "",
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the diagnosis:',
        '```text',
        'keywords: keyword1, keyword2, keyword3',
        ' -- ',
        'theComment',
        '```',
        '',
        'Among the following conditions, identify the most relevant one:',
        '',
        ' * labelA (ICD-10: code12.3)\n * labelB (ICD-10: code36.9)\n * labelC (ICD-10: code75.2)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"ICD10": "the ICD-10 code", "label": "the label"}]',
        '```',
        '',
    ]
    keywords = ['keyword1', 'keyword2', 'keyword3', "ICD01", "ICD02", "ICD03"]
    search = [
        Icd10Condition(code="code123", label="labelA"),
        Icd10Condition(code="code369", label="labelB"),
        Icd10Condition(code="code752", label="labelC"),
    ]

    # all good
    search_conditions.side_effect = [search]
    single_conversation.side_effect = [[{"ICD10": "CODE98.76", "label": "theCondition"}]]

    result = tested.condition_from(settings, keywords[:3], keywords[3:], "theComment")
    expected = CodedItem(label="theCondition", code="CODE9876", uuid="")
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert search_conditions.mock_calls == calls
    calls = [call(settings, system_prompt, user_prompt)]
    assert single_conversation.mock_calls == calls
    reset_mocks()

    # no condition found
    search_conditions.side_effect = [[]]
    single_conversation.side_effect = []

    result = tested.condition_from(settings, keywords[:3], keywords[3:], "theComment")
    expected = CodedItem(label="", code="", uuid="")
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert search_conditions.mock_calls == calls
    assert single_conversation.mock_calls == []
    reset_mocks()

    # no response
    search_conditions.side_effect = [search]
    single_conversation.side_effect = [[]]

    result = tested.condition_from(settings, keywords[:3], keywords[3:], "theComment")
    expected = CodedItem(label="", code="", uuid="")
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert search_conditions.mock_calls == calls
    calls = [call(settings, system_prompt, user_prompt)]
    assert single_conversation.mock_calls == calls
    reset_mocks()


@patch.object(SelectorChat, "single_conversation")
@patch.object(DataLabTestView, "objects")
def test_lab_test_from(lab_test, single_conversation):
    def reset_mocks():
        lab_test.reset_mock()
        single_conversation.reset_mock()

    tested = SelectorChat

    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to select the most relevant lab test for a patient out of a list of lab tests.",
        "",
    ]
    user_prompts = [
        [
            'Here is the comment provided by the healthcare provider in regards to the lab test to be ordered for the patient:',
            '```text',
            'keywords: word1 word2 word3,  word4  ',
            ' -- ',
            'theComment',
            '```',
            '',
            "The lab test is intended to the patient's conditions: theCondition1, theCondition2.",
            '',
            'Among the following lab tests, select the most relevant one:',
            '',
            ' * labelA (code: code123)\n'
            ' * labelB (code: code369)\n'
            ' * labelC (code: code752)\n'
            ' * labelA (code: code123)\n'
            ' * labelB (code: code369)\n'
            ' * labelC (code: code752)',
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            '[{"code": "the lab test code", "label": "the lab test label"}]',
            '```',
            '',
        ],
        [
            'Here is the comment provided by the healthcare provider in regards to the lab test to be ordered for the patient:',
            '```text',
            'keywords: word1 word2 word3,  word4  ',
            ' -- ',
            'theComment',
            '```',
            '',
            "",
            '',
            'Among the following lab tests, select the most relevant one:',
            '',
            ' * labelA (code: code123)\n'
            ' * labelB (code: code369)\n'
            ' * labelC (code: code752)\n'
            ' * labelA (code: code123)\n'
            ' * labelB (code: code369)\n'
            ' * labelC (code: code752)',
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            '[{"code": "the lab test code", "label": "the lab test label"}]',
            '```',
            '',
        ],
    ]
    lab_tests = [
        DataLabTestView(order_code="code123", order_name="labelA"),
        DataLabTestView(order_code="code369", order_name="labelB"),
        DataLabTestView(order_code="code752", order_name="labelC"),
    ]
    expressions = [
        "word1 word2 word3",
        " word4  ",
    ]
    conditions = ["theCondition1", "theCondition2"]

    # all good
    # -- with conditions
    lab_test.filter.return_value.filter.side_effect = [lab_tests, lab_tests]
    single_conversation.side_effect = [[{"code": "CODE9876", "label": "theLabTest"}]]

    result = tested.lab_test_from(settings, "theLabPartner", expressions, "theComment", conditions)
    expected = CodedItem(label="theLabTest", code="CODE9876", uuid="")
    assert result == expected
    calls = [
        call.filter(lab__name='theLabPartner'),
        call.filter().filter(Q(('keywords__icontains', 'word1'), ('keywords__icontains', 'word2'), ('keywords__icontains', 'word3'))),
        call.filter(lab__name='theLabPartner'),
        call.filter().filter(Q(('keywords__icontains', 'word4'))),
    ]
    assert lab_test.mock_calls == calls
    calls = [call(settings, system_prompt, user_prompts[0])]
    assert single_conversation.mock_calls == calls
    reset_mocks()
    # -- without conditions
    lab_test.filter.return_value.filter.side_effect = [lab_tests, lab_tests]
    single_conversation.side_effect = [[{"code": "CODE9876", "label": "theLabTest"}]]

    result = tested.lab_test_from(settings, "theLabPartner", expressions, "theComment", [])
    expected = CodedItem(label="theLabTest", code="CODE9876", uuid="")
    assert result == expected
    calls = [
        call.filter(lab__name='theLabPartner'),
        call.filter().filter(Q(('keywords__icontains', 'word1'), ('keywords__icontains', 'word2'), ('keywords__icontains', 'word3'))),
        call.filter(lab__name='theLabPartner'),
        call.filter().filter(Q(('keywords__icontains', 'word4'))),
    ]
    assert lab_test.mock_calls == calls
    calls = [call(settings, system_prompt, user_prompts[1])]
    assert single_conversation.mock_calls == calls
    reset_mocks()

    # no response
    lab_test.filter.return_value.filter.side_effect = [lab_tests, lab_tests]
    single_conversation.side_effect = [[]]

    result = tested.lab_test_from(settings, "theLabPartner", expressions, "theComment", conditions)
    expected = CodedItem(label="", code="", uuid="")
    assert result == expected
    calls = [
        call.filter(lab__name='theLabPartner'),
        call.filter().filter(Q(('keywords__icontains', 'word1'), ('keywords__icontains', 'word2'), ('keywords__icontains', 'word3'))),
        call.filter(lab__name='theLabPartner'),
        call.filter().filter(Q(('keywords__icontains', 'word4'))),
    ]
    assert lab_test.mock_calls == calls
    calls = [call(settings, system_prompt, user_prompts[0])]
    assert single_conversation.mock_calls == calls
    reset_mocks()

    # no lab test
    lab_test.filter.return_value.filter.side_effect = [[], []]
    single_conversation.side_effect = []

    result = tested.lab_test_from(settings, "theLabPartner", expressions, "theComment", conditions)
    expected = CodedItem(label="", code="", uuid="")
    assert result == expected
    calls = [
        call.filter(lab__name='theLabPartner'),
        call.filter().filter(Q(('keywords__icontains', 'word1'), ('keywords__icontains', 'word2'), ('keywords__icontains', 'word3'))),
        call.filter(lab__name='theLabPartner'),
        call.filter().filter(Q(('keywords__icontains', 'word4'))),
    ]
    assert lab_test.mock_calls == calls
    assert single_conversation.mock_calls == []
    reset_mocks()


@patch('commander.protocols.selector_chat.OpenaiChat')
def test_single_conversation(chat):
    mock = MagicMock()

    def reset_mocks():
        chat.reset_mock()
        mock.reset_mock()

    settings = Settings(
        openai_key="openaiKey",
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        allow_update=True,
    )
    system_prompt = ["theSystemPrompt"]
    user_prompt = ["theUserPrompt"]
    tested = SelectorChat

    # without error
    chat.side_effect = [mock]
    mock.chat.side_effect = [JsonExtract(error="theError", has_error=False, content=["theContent"])]
    result = tested.single_conversation(settings, system_prompt, user_prompt)
    assert result == ["theContent"]

    calls = [call('openaiKey', 'gpt-4o')]
    assert chat.mock_calls == calls
    assert mock.system_prompt == system_prompt
    assert mock.user_prompt == user_prompt
    calls = [call.chat()]
    assert mock.mock_calls == calls
    reset_mocks()

    # with error
    chat.side_effect = [mock]
    mock.chat.side_effect = [JsonExtract(error="theError", has_error=True, content=["theContent"])]
    result = tested.single_conversation(settings, system_prompt, user_prompt)
    assert result == []

    calls = [call('openaiKey', 'gpt-4o')]
    assert chat.mock_calls == calls
    assert mock.system_prompt == system_prompt
    assert mock.user_prompt == user_prompt
    calls = [call.chat()]
    assert mock.mock_calls == calls
    reset_mocks()
