from datetime import date
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.past_surgical_history import PastSurgicalHistoryCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.surgery_history import SurgeryHistory
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medical_concept import MedicalConcept
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> SurgeryHistory:
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
    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return SurgeryHistory(settings, cache, identification)


def test_class():
    tested = SurgeryHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = SurgeryHistory
    result = tested.schema_key()
    expected = "surgicalHistory"
    assert result == expected


def test_staged_command_extract():
    tested = SurgeryHistory
    tests = [
        ({}, None),
        ({
             "comment": "theComment",
             "approximate_date": {"date": "theDate"},
             "past_surgical_history": {
                 "text": "theSurgery",
                 "value": 40653006,
             }
         }, CodedItem(label="theSurgery: theComment (on: theDate)", code="40653006", uuid="")),
        ({
             "comment": "theComment",
             "approximate_date": {"date": "theDate"},
             "past_surgical_history": {
                 "text": "",
                 "value": 40653006,
             }
         }, None),
        ({
             "comment": "theComment",
             "approximate_date": {"date": ""},
             "past_surgical_history": {
                 "text": "theSurgery",
                 "value": 40653006,
             }
         }, CodedItem(label="theSurgery: theComment (on: n/a)", code="40653006", uuid="")),
        ({
             "comment": "",
             "approximate_date": {"date": "theDate"},
             "past_surgical_history": {
                 "text": "theSurgery",
                 "value": 40653006,
             }
         }, CodedItem(label="theSurgery: n/a (on: theDate)", code="40653006", uuid="")),
        ({
             "comment": "theComment",
             "approximate_date": {"date": "theDate"},
             "past_surgical_history": {
                 "text": "theSurgery",
                 "value": 40653006,
             }
         }, CodedItem(label="theSurgery: theComment (on: theDate)", code="40653006", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "surgical_histories")
def test_command_from_json(surgical_histories):
    chatter = MagicMock()

    def reset_mocks():
        surgical_histories.reset_mock()
        chatter.reset_mock()

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
        '[{"conceptId": "the concept ID", "term": "the expression"}]',
        '```',
        '',
    ]
    schemas = [{
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {'conceptId': {'type': 'string', 'minLength': 1},
                           'term': {'type': 'string', 'minLength': 1},
                           },
            'required': ['conceptId', 'term'],
            'additionalProperties': False,
        }, 'minItems': 1,
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
            "approximateDate": "2017-05-21",
            "comment": "theComment",
        },
    }
    medications = [
        MedicalConcept(concept_id=123, term="termA"),
        MedicalConcept(concept_id=369, term="termB"),
        MedicalConcept(concept_id=752, term="termC"),
    ]

    # all good
    surgical_histories.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"concept_id": 369, "term": "termB"}]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = PastSurgicalHistoryCommand(
        approximate_date=date(2017, 5, 21),
        past_surgical_history="termB",
        comment="theComment",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert surgical_histories.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    surgical_histories.side_effect = [medications]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = PastSurgicalHistoryCommand(
        approximate_date=date(2017, 5, 21),
        comment="theComment",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert surgical_histories.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    surgical_histories.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = PastSurgicalHistoryCommand(
        approximate_date=date(2017, 5, 21),
        comment="theComment",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert surgical_histories.mock_calls == calls
    assert chatter.mock_calls == []
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


@patch.object(LimitedCache, "surgery_history")
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
