from datetime import date
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.medical_history import MedicalHistoryCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.medical_history import MedicalHistory
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.icd10_condition import Icd10Condition
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> MedicalHistory:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
    )
    cache = LimitedCache("patientUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return MedicalHistory(settings, cache, identification)


def test_class():
    tested = MedicalHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = MedicalHistory
    result = tested.schema_key()
    expected = "medicalHistory"
    assert result == expected


def test_staged_command_extract():
    tested = MedicalHistory
    tests = [
        ({}, None),
        ({
             "comments": "theComment",
             "approximate_end_date": {"date": "endDate"},
             "past_medical_history": {"text": "theCondition"},
             "approximate_start_date": {"date": "startDate"},
         }, CodedItem(label="theCondition: from startDate to endDate (theComment)", code="", uuid="")),
        ({
             "comments": "theComment",
             "approximate_end_date": {"date": "endDate"},
             "past_medical_history": {"text": ""},
             "approximate_start_date": {"date": "startDate"},
         }, None),
        ({
             "comments": "",
             "approximate_end_date": {"date": "endDate"},
             "past_medical_history": {"text": "theCondition"},
             "approximate_start_date": {"date": "startDate"},
         }, CodedItem(label="theCondition: from startDate to endDate (n/a)", code="", uuid="")),
        ({
             "comments": "theComment",
             "approximate_end_date": {"date": "endDate"},
             "past_medical_history": {"text": "theCondition"},
             "approximate_start_date": {"date": ""},
         }, CodedItem(label="theCondition: from n/a to endDate (theComment)", code="", uuid="")),
        ({
             "comments": "theComment",
             "approximate_end_date": {"date": ""},
             "past_medical_history": {"text": "theCondition"},
             "approximate_start_date": {"date": "startDate"},
         }, CodedItem(label="theCondition: from startDate to n/a (theComment)", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "medical_histories")
def test_command_from_json(medical_histories):
    chatter = MagicMock()

    def reset_mocks():
        medical_histories.reset_mock()
        chatter.reset_mock()

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
        '[{"ICD10": "the ICD-10 code", "label": "the label"}]',
        '```',
        '',
    ]
    schemas = [{
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
    keywords = ['keyword1', 'keyword2', 'keyword3']
    tested = helper_instance()

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            'keywords': 'keyword1,keyword2,keyword3',
            "approximateStartDate": "2018-03-15",
            "approximateEndDate": "2021-07-19",
            'comments': 'theComment',
        },
    }
    conditions = [
        Icd10Condition(code="code123", label="labelA"),
        Icd10Condition(code="code369", label="labelB"),
        Icd10Condition(code="code752", label="labelC"),
    ]

    # all good
    medical_histories.side_effect = [conditions]
    chatter.single_conversation.side_effect = [[{"ICD10": "code369", "label": "labelB"}]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = MedicalHistoryCommand(
        approximate_start_date=date(2018, 3, 15),
        approximate_end_date=date(2021, 7, 19),
        show_on_condition_list=True,
        comments="theComment",
        past_medical_history="labelB",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medical_histories.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    medical_histories.side_effect = [conditions]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = MedicalHistoryCommand(
        approximate_start_date=date(2018, 3, 15),
        approximate_end_date=date(2021, 7, 19),
        show_on_condition_list=True,
        comments="theComment",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medical_histories.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    medical_histories.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = MedicalHistoryCommand(
        approximate_start_date=date(2018, 3, 15),
        approximate_end_date=date(2021, 7, 19),
        show_on_condition_list=True,
        comments="theComment",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert medical_histories.mock_calls == calls
    assert chatter.mock_calls == []
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


@patch.object(LimitedCache, "condition_history")
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
