from hashlib import md5
import json
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.instruct import InstructCommand
from canvas_sdk.commands.constants import Coding

from hyperscribe.commands.base import Base
from hyperscribe.commands.instruct import Instruct
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.custom_prompt import CustomPrompt
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medical_concept import MedicalConcept
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance(custom_prompts: list[CustomPrompt] = None) -> Instruct:
    if custom_prompts is None:
        custom_prompts = []
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=custom_prompts,
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
    return Instruct(settings, cache, identification)


def test_class():
    tested = Instruct
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Instruct
    result = tested.schema_key()
    expected = "instruct"
    assert result == expected


def test_note_section():
    tested = Instruct
    result = tested.note_section()
    expected = "Plan"
    assert result == expected


def test_staged_command_extract():
    tested = Instruct
    tests = [
        ({}, None),
        (
            {"instruct": {"text": "theInstruction"}, "narrative": "theNarrative"},
            CodedItem(label="theInstruction (theNarrative)", code="", uuid=""),
        ),
        (
            {"instruct": {"text": "theInstruction"}, "narrative": ""},
            CodedItem(label="theInstruction (n/a)", code="", uuid=""),
        ),
        ({"instruct": {"text": ""}, "narrative": "theNarrative"}, None),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "instructions")
@patch.object(Instruct, "add_code2description")
def test_command_from_json(add_code2description, instructions):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        instructions.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant direction.",
        "",
    ]
    user_prompt = [
        "Here is the description of a direction instructed by a healthcare provider to a patient:",
        "```text",
        "keywords: keyword1,keyword2,keyword3",
        " -- ",
        "theComment",
        "```",
        "Among the following expressions, identify the most relevant one:",
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
        "parameters": {"keywords": "keyword1,keyword2,keyword3", "comment": "theComment"},
    }
    medical_concepts = [
        MedicalConcept(concept_id=123, term="termA"),
        MedicalConcept(concept_id=369, term="termB"),
        MedicalConcept(concept_id=752, term="termC"),
    ]

    # all good
    instructions.side_effect = [medical_concepts]
    chatter.single_conversation.side_effect = [[{"conceptId": 369, "term": "termB"}]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = InstructCommand(
        coding=Coding(code="369", system="http://snomed.info/sct", display="termB"),
        comment="theComment",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert instructions.mock_calls == calls
    calls = [call(369, "")]
    assert add_code2description.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    instructions.side_effect = [medical_concepts]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = InstructCommand(comment="theComment", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert instructions.mock_calls == calls
    assert add_code2description.mock_calls == []
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    instructions.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = InstructCommand(comment="theComment", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call(keywords)]
    assert instructions.mock_calls == calls
    assert add_code2description.mock_calls == []
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "",
        "comment": "",
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 1
    schema = schemas[0]

    #
    schema_hash = md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "adf009d69cd83beebd42f143f449ed37"
    assert schema_hash == expected_hash

    tests = [
        (
            [{"keywords": "diet,nutrition,lifestyle", "comment": "Patient should follow a low-sodium diet"}],
            "",
        ),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {"keywords": "diet,nutrition", "comment": "Follow low-sodium diet"},
                {"keywords": "exercise", "comment": "Walk 30 minutes daily"},
            ],
            "[{'keywords': 'diet,nutrition', 'comment': 'Follow low-sodium diet'}, "
            "{'keywords': 'exercise', 'comment': 'Walk 30 minutes daily'}] is too long",
        ),
        (
            [{"keywords": "diet", "comment": "Follow low-sodium diet", "extra": "field"}],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        (
            [{"comment": "Follow low-sodium diet"}],
            "'keywords' is a required property, in path [0]",
        ),
        (
            [{"keywords": "diet"}],
            "'comment' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_instruction_description():
    # without custom prompt
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Specific or standard direction. "
        "There can be only one direction per instruction, and no instruction in the lack of."
    )
    assert result == expected
    #
    # with custom prompt
    tested = helper_instance(
        custom_prompts=[
            CustomPrompt(
                command="Instruct",
                prompt="custom prompt text",
                active=True,
            )
        ]
    )
    result = tested.instruction_description()
    expected = (
        "Specific or standard direction. "
        "There can be only one direction per instruction, and no instruction in the lack of."
        "For documentation purpose, always add the parts of the transcript used."
    )
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
