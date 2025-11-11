from hashlib import md5
import json
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.family_history import FamilyHistoryCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.family_history import FamilyHistory
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
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
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
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


def test_note_section():
    tested = FamilyHistory
    result = tested.note_section()
    expected = "History"
    assert result == expected


def test_staged_command_extract():
    tested = FamilyHistory
    tests = [
        ({}, None),
        (
            {"relative": {"text": "theRelative"}, "family_history": {"text": "theFamilyHistory"}},
            CodedItem(label="theRelative: theFamilyHistory", code="", uuid=""),
        ),
        ({"relative": {"text": "theRelative"}, "family_history": {"text": ""}}, None),
        ({"relative": {"text": ""}, "family_history": {"text": "theFamilyHistory"}}, None),
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
        "Here is the note provided by the healthcare provider in regards to the condition of a patient:",
        "```text",
        "keywords: keyword1,keyword2,keyword3",
        " -- ",
        "theNote",
        "```",
        "Among the following conditions, identify the most relevant one:",
        "",
        " * termA (conceptId: '123')\n * termB (conceptId: '369')\n * termC (conceptId: '752')",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"conceptId": "the concept id, as string", "term": "the expression"}]',
        "```",
        "",
    ]
    schemas = [
        {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "conceptId": {"type": "string", "minLength": 1},
                    "term": {"type": "string", "minLength": 1},
                },
                "required": ["conceptId", "term"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "maxItems": 1,
        },
    ]
    keywords = ["keyword1", "keyword2", "keyword3"]
    tested = helper_instance()

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "previous_information": "thePreviousInformation",
        "parameters": {
            "keywords": "keyword1,keyword2,keyword3",
            "relative": "sibling",
            "note": "theNote",
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
    command = FamilyHistoryCommand(relative="sibling", note="theNote", family_history="termB", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert family_histories.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    family_histories.side_effect = [medical_concepts]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = FamilyHistoryCommand(relative="sibling", note="theNote", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert family_histories.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    family_histories.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = FamilyHistoryCommand(relative="sibling", note="theNote", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert family_histories.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "",
        "relative": "",
        "note": "",
    }
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Any relevant condition of a relative among: "
        "father, mother, parent, child, brother, sister, sibling, grand-parent, grand-father, grand-mother. "
        "There can be only one condition per relative per instruction, and no instruction in the lack of."
    )
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
        (
            allergies,
            "Only document 'FamilyHistory' for information outside the following list: "
            "display1a, display2a, display3a.",
        ),
        ([], ""),
    ]
    for side_effect, expected in tests:
        family_history.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert family_history.mock_calls == calls
        reset_mocks()


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 1
    schema = schemas[0]

    #
    schema_hash = md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "c1d479de900bc36cee8c956843371baa"
    assert schema_hash == expected_hash

    tests = [
        (
            [{"keywords": "diabetes,T2DM", "relative": "father", "note": "Patient's father has diabetes"}],
            "",
        ),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {"keywords": "diabetes", "relative": "father", "note": "Patient's father has diabetes"},
                {"keywords": "hypertension", "relative": "mother", "note": "Patient's mother has hypertension"},
            ],
            "[{'keywords': 'diabetes', 'relative': 'father', 'note': \"Patient's father has diabetes\"}, "
            "{'keywords': 'hypertension', 'relative': 'mother', 'note': \"Patient's mother has hypertension\"}] "
            "is too long",
        ),
        (
            [{"keywords": "diabetes", "relative": "father", "note": "Patient's father has diabetes", "extra": "field"}],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        (
            [{"relative": "father", "note": "Patient's father has diabetes"}],
            "'keywords' is a required property, in path [0]",
        ),
        (
            [{"keywords": "diabetes", "note": "Patient's father has diabetes"}],
            "'relative' is a required property, in path [0]",
        ),
        (
            [{"keywords": "diabetes", "relative": "father"}],
            "'note' is a required property, in path [0]",
        ),
        (
            [{"keywords": "diabetes", "relative": "uncle", "note": "Patient's uncle has diabetes"}],
            "'uncle' is not one of ['father', 'mother', 'parent', 'child', 'brother', 'sister', 'sibling', "
            "'grand-parent', 'grand-father', 'grand-mother'], in path [0, 'relative']",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
