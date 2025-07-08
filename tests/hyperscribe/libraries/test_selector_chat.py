from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.constants import ServiceProvider

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.icd10_condition import Icd10Condition
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


@patch.object(CanvasScience, "search_conditions")
def test_condition_from(search_conditions):
    chatter = MagicMock()

    def reset_mocks():
        search_conditions.reset_mock()
        chatter.reset_mock()

    tested = SelectorChat

    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        is_tuning=False,

        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
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
    schemas = [{''
                '$schema': 'http://json-schema.org/draft-07/schema#',
                'type': 'array',
                'items': {
                    'type': 'object',
                    'properties': {
                        'ICD10': {'type': 'string', 'minLength': 1},
                        'label': {'type': 'string', 'minLength': 1},
                    },
                    'required': ['ICD10', 'label'],
                    'additionalProperties': False,
                },
                'minItems': 1,
                'maxItems': 1,
                }]
    keywords = ['keyword1', 'keyword2', 'keyword3', "ICD01", "ICD02", "ICD03"]
    search = [
        Icd10Condition(code="code123", label="labelA"),
        Icd10Condition(code="code369", label="labelB"),
        Icd10Condition(code="code752", label="labelC"),
    ]
    instruction = Instruction(
        uuid="theUuid",
        index=0,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
    )
    # all good
    search_conditions.side_effect = [search]
    chatter.single_conversation.side_effect = [[{"ICD10": "CODE98.76", "label": "theCondition"}]]

    result = tested.condition_from(instruction, chatter, settings, keywords[:3], keywords[3:], "theComment")
    expected = CodedItem(label="theCondition", code="CODE9876", uuid="")
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert search_conditions.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no condition found
    search_conditions.side_effect = [[]]
    chatter.single_conversation.side_effect = []

    result = tested.condition_from(instruction, chatter, settings, keywords[:3], keywords[3:], "theComment")
    expected = CodedItem(label="", code="", uuid="")
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert search_conditions.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # no response
    search_conditions.side_effect = [search]
    chatter.single_conversation.side_effect = [[]]

    result = tested.condition_from(instruction, chatter, settings, keywords[:3], keywords[3:], "theComment")
    expected = CodedItem(label="", code="", uuid="")
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert search_conditions.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.selector_chat.LimitedCache")
def test_lab_test_from(limited_cache):
    chatter = MagicMock()

    def reset_mocks():
        limited_cache.reset_mock()
        chatter.reset_mock()

    tested = SelectorChat

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
            ' * labelC (code: code752)',
            '',
            'Please, present your findings in a JSON format within a Markdown code block like:',
            '```json',
            '[{"code": "the lab test code", "label": "the lab test label"}]',
            '```',
            '',
        ],
    ]
    schemas = [{
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'code': {'type': 'string', 'minLength': 1},
                'label': {'type': 'string', 'minLength': 1},
            },
            'required': ['code', 'label'],
            'additionalProperties': False,
        },
        'minItems': 1,
        'maxItems': 1,
    }]
    lab_tests = [
        CodedItem(code="code123", label="labelA", uuid=""),
        CodedItem(code="code369", label="labelB", uuid=""),
        CodedItem(code="code752", label="labelC", uuid=""),
    ]
    expressions = [
        "word1 word2 word3",
        " word4  ",
    ]
    conditions = ["theCondition1", "theCondition2"]
    instruction = Instruction(
        uuid="theUuid",
        index=0,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
    )

    # all good
    # -- with conditions
    limited_cache.lab_tests.side_effect = [lab_tests, lab_tests]
    chatter.single_conversation.side_effect = [[{"code": "CODE9876", "label": "theLabTest"}]]

    result = tested.lab_test_from(instruction, chatter, limited_cache, "theLabPartner", expressions, "theComment", conditions)
    expected = CodedItem(label="theLabTest", code="CODE9876", uuid="")
    assert result == expected
    calls = [
        call.lab_tests('theLabPartner', ['word1', 'word2', 'word3']),
        call.lab_tests('theLabPartner', ['word4']),
    ]
    assert limited_cache.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts[0], schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()
    # -- without conditions
    limited_cache.lab_tests.side_effect = [lab_tests, lab_tests]
    chatter.single_conversation.side_effect = [[{"code": "CODE9876", "label": "theLabTest"}]]

    result = tested.lab_test_from(instruction, chatter, limited_cache, "theLabPartner", expressions, "theComment", [])
    expected = CodedItem(label="theLabTest", code="CODE9876", uuid="")
    assert result == expected
    calls = [
        call.lab_tests('theLabPartner', ['word1', 'word2', 'word3']),
        call.lab_tests('theLabPartner', ['word4']),
    ]
    assert limited_cache.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts[1], schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no response
    limited_cache.lab_tests.side_effect = [lab_tests, lab_tests]
    chatter.single_conversation.side_effect = [[]]

    result = tested.lab_test_from(instruction, chatter, limited_cache, "theLabPartner", expressions, "theComment", conditions)
    expected = CodedItem(label="", code="", uuid="")
    assert result == expected
    calls = [
        call.lab_tests('theLabPartner', ['word1', 'word2', 'word3']),
        call.lab_tests('theLabPartner', ['word4']),
    ]
    assert limited_cache.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompts[0], schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no lab test
    limited_cache.lab_tests.side_effect = [[], []]
    chatter.single_conversation.side_effect = []

    result = tested.lab_test_from(instruction, chatter, limited_cache, "theLabPartner", expressions, "theComment", conditions)
    expected = CodedItem(label="", code="", uuid="")
    assert result == expected
    calls = [
        call.lab_tests('theLabPartner', ['word1', 'word2', 'word3']),
        call.lab_tests('theLabPartner', ['word4']),
    ]
    assert limited_cache.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


@patch.object(SelectorChat, "summary_of")
@patch.object(CanvasScience, "search_contacts")
def test_contact_from(search_contacts, summary_of):
    chatter = MagicMock()

    def reset_mocks():
        search_contacts.reset_mock()
        summary_of.reset_mock()
        chatter.reset_mock()

    tested = SelectorChat

    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant contact in regards of a search specialist out of a list of contacts.",
        "",
    ]
    user_prompt = [
        'Here is the comment provided by the healthcare provider in regards to the searched specialist:',
        '```text', 'theFreeTextInformation',
        '```',
        '',
        'Among the following contacts, identify the most relevant one:',
        '',
        ' * theSummary1 (index: 0)\n * theSummary2 (index: 1)\n * theSummary3 (index: 2)',
        '',
        'Please, present your findings in a JSON format within a Markdown code block like:',
        '```json',
        '[{"index": "the index, as integer", "contact": "the contact information"}]',
        '```',
        '',
    ]

    search = [
        ServiceProvider(
            first_name="theFirstName1",
            last_name="theLastName1",
            specialty="theSpecialty1",
            practice_name="thePracticeName1",
            business_address="theBusinessAddress1",
        ),
        ServiceProvider(
            first_name="theFirstName2",
            last_name="theLastName2",
            specialty="theSpecialty2",
            practice_name="thePracticeName2",
            business_address="theBusinessAddress2",
        ),
        ServiceProvider(
            first_name="theFirstName3",
            last_name="theLastName3",
            specialty="theSpecialty3",
            practice_name="thePracticeName3",
            business_address="theBusinessAddress3",
        ),
    ]
    summaries = [
        "theSummary1",
        "theSummary2",
        "theSummary3",
    ]
    instruction = Instruction(
        uuid="theUuid",
        index=0,
        instruction="theInstruction",
        information="theInformation",
        is_new=True,
        is_updated=True,
    )
    schemas = [{
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "array",
        "items": {
            "type": "object",
            "properties": {
                "index": {
                    "type": "integer",
                    "description": "the index as provided in the list",
                },
                "contact": {
                    "type": "string",
                    "description": "the contact information as provided in the list",
                },
            },
            "required": ["index", "contact"],
            "additionalProperties": False,
        }
    }]

    # all good
    search_contacts.side_effect = [search]
    summary_of.side_effect = summaries
    chatter.single_conversation.side_effect = [[{"index": 1, "label": "theLabel"}]]

    result = tested.contact_from(instruction, chatter, settings, "theFreeTextInformation", ["zip1", "zip2"])
    expected = ServiceProvider(
        first_name="theFirstName2",
        last_name="theLastName2",
        specialty="theSpecialty2",
        practice_name="thePracticeName2",
        business_address="theBusinessAddress2",
    )
    assert result == expected
    calls = [call('scienceHost', "theFreeTextInformation", ["zip1", "zip2"])]
    assert search_contacts.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # incorrect index
    search_contacts.side_effect = [search]
    summary_of.side_effect = summaries
    chatter.single_conversation.side_effect = [[{"index": -1, "label": "theLabel"}]]

    result = tested.contact_from(instruction, chatter, settings, "theFreeTextInformation", ["zip1", "zip2"])
    expected = ServiceProvider(first_name="TBD", last_name="", specialty="TBD", practice_name="")
    assert result == expected
    calls = [call('scienceHost', "theFreeTextInformation", ["zip1", "zip2"])]
    assert search_contacts.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no condition found
    search_contacts.side_effect = [[]]
    summary_of.side_effect = []
    chatter.single_conversation.side_effect = []

    result = tested.contact_from(instruction, chatter, settings, "theFreeTextInformation", ["zip1", "zip2"])
    expected = ServiceProvider(first_name="TBD", last_name="", specialty="TBD", practice_name="")
    assert result == expected
    calls = [call('scienceHost', "theFreeTextInformation", ["zip1", "zip2"])]
    assert search_contacts.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # no response
    search_contacts.side_effect = [search]
    summary_of.side_effect = summaries
    chatter.single_conversation.side_effect = [[]]

    result = tested.contact_from(instruction, chatter, settings, "theFreeTextInformation", ["zip1", "zip2"])
    expected = ServiceProvider(first_name="TBD", last_name="", specialty="TBD", practice_name="")
    assert result == expected
    calls = [call('scienceHost', "theFreeTextInformation", ["zip1", "zip2"])]
    assert search_contacts.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()


def test_summary_of():
    tests = [
        (ServiceProvider(
            first_name="theFirstName1",
            last_name="theLastName1",
            specialty="theSpecialty1",
            practice_name="thePracticeName1",
            business_address="theBusinessAddress1",
        ), "theFirstName1 theLastName1 / theSpecialty1 (theBusinessAddress1)"),
        (ServiceProvider(
            first_name="theFirstName1",
            last_name="",
            specialty="theSpecialty1",
            practice_name="thePracticeName1",
            business_address="theBusinessAddress1",
        ), "theFirstName1 / theSpecialty1 (theBusinessAddress1)"),
        (ServiceProvider(
            first_name="",
            last_name="theLastName1",
            specialty="theSpecialty1",
            practice_name="thePracticeName1",
            business_address="theBusinessAddress1",
        ), "theLastName1 / theSpecialty1 (theBusinessAddress1)"),
        (ServiceProvider(
            first_name="",
            last_name="",
            specialty="theSpecialty1",
            practice_name="thePracticeName1",
            business_address="theBusinessAddress1",
        ), "theSpecialty1 (theBusinessAddress1)"),
        (ServiceProvider(
            first_name="theFirstName1",
            last_name="theLastName1",
            specialty="",
            practice_name="",
            business_address="",
        ), "theFirstName1 theLastName1"),
        (ServiceProvider(
            first_name="",
            last_name="",
            specialty="",
            practice_name="",
            business_address="theBusinessAddress1",
        ), "theBusinessAddress1"),
    ]
    tested = SelectorChat
    for service_provider, expected in tests:
        result = tested.summary_of(service_provider)
        assert result == expected, f"--> {service_provider}"
