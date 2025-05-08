from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.family_history import FamilyHistoryCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.family_history import FamilyHistory
from hyperscribe.handlers.canvas_science import CanvasScience
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medical_concept import MedicalConcept
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> FamilyHistory:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
    )
    cache = LimitedCache("patientUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return FamilyHistory(settings, cache, identification)


def test_class():
    tested = FamilyHistory
    assert issubclass(tested, Base)


def test_schema_key():
    tested = FamilyHistory
    result = tested.schema_key()
    expected = "familyHistory"
    assert result == expected


def test_staged_command_extract():
    tested = FamilyHistory
    tests = [
        ({}, None),
        ({
             "relative": {"text": "theRelative"},
             "family_history": {"text": "theFamilyHistory"}
         }, CodedItem(label="theRelative: theFamilyHistory", code="", uuid="")),
        ({
             "relative": {"text": "theRelative"},
             "family_history": {"text": ""}
         }, None),
        ({
             "relative": {"text": ""},
             "family_history": {"text": "theFamilyHistory"}
         }, None),

    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "family_histories")
def test_command_from_json(family_histories):
    chatter = MagicMock()

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
        '```json', '[{"conceptId": "the concept ID", "term": "the expression"}]',
        '```',
        '',
    ]
    schemas = [{
        '$schema': 'http://json-schema.org/draft-07/schema#',
        'type': 'array',
        'items': {
            'type': 'object',
            'properties': {
                'conceptId': {'type': 'string', 'minLength': 1},
                'term': {'type': 'string', 'minLength': 1},
            },
            'required': ['conceptId', 'term'],
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
        "audits": ["theAudit"],
        "parameters": {
            'keywords': 'keyword1,keyword2,keyword3',
            'relative': 'sibling',
            'note': 'theNote',
        },
    }
    medical_concepts = [
        MedicalConcept(concept_id=123, term="termA"),
        MedicalConcept(concept_id=369, term="termB"),
        MedicalConcept(concept_id=752, term="termC"),
    ]

    # all good
    family_histories.side_effect = [medical_concepts]
    chatter.single_conversation.side_effect = [[{"conceptId": 369, "term": "termB"}]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = FamilyHistoryCommand(
        relative="sibling",
        note="theNote",
        family_history="termB",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert family_histories.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    family_histories.side_effect = [medical_concepts]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = FamilyHistoryCommand(
        relative="sibling",
        note="theNote",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call('scienceHost', keywords)]
    assert family_histories.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    family_histories.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = FamilyHistoryCommand(
        relative="sibling",
        note="theNote",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
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


@patch.object(LimitedCache, "family_history")
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
