from datetime import date
from hashlib import md5
import json
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.allergy import AllergyCommand, Allergen, AllergenType

from hyperscribe.commands.allergy import Allergy
from hyperscribe.commands.base import Base
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.allergy_detail import AllergyDetail
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Allergy:
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
    return Allergy(settings, cache, identification)


def test_class():
    tested = Allergy
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Allergy
    result = tested.schema_key()
    expected = "allergy"
    assert result == expected


def test_note_section():
    tested = Allergy
    result = tested.note_section()
    expected = "History"
    assert result == expected


def test_staged_command_extract():
    tested = Allergy
    tests = [
        ({}, None),
        ({"allergy": {"text": "theAllergy", "value": 123456}}, CodedItem(label="theAllergy", code="123456", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "search_allergy")
@patch.object(Allergy, "add_code2description")
def test_command_from_json(add_code2description, search_allergy):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        search_allergy.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant allergy of a patient out of a list of allergies.",
        "",
    ]
    user_prompt = [
        "Here is the comment provided by the healthcare provider in regards to the allergy:",
        "```text",
        "keywords: keyword1,keyword2,keyword3",
        " -- ",
        "severity: moderate",
        "",
        "theReaction",
        "```",
        "",
        "Among the following allergies, identify the most relevant one:",
        "",
        " * descriptionA (conceptId: 134)\n * descriptionB (conceptId: 167)\n * descriptionC (conceptId: 234)",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"conceptId": "the concept id, as int", "term": "the description"}]',
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

    tests = [
        ("allergy group", 1, 1),
        ("medication", 2, 1),
        ("medication", 2, 2),
        ("ingredient", 6, 1),
        ("ingredient", 6, 6),
    ]
    for concept_type, exp_concept_id_type, selected_concept_id_type in tests:
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "approximateDateOfOnset": "2025-02-04",
                "keywords": "keyword1,keyword2,keyword3",
                "reaction": "theReaction",
                "severity": "moderate",
                "type": concept_type,
            },
        }
        allergy_details = [
            AllergyDetail(
                concept_id_value=134,
                concept_id_description="descriptionA",
                concept_type="conceptTypeA",
                concept_id_type=1,
            ),
            AllergyDetail(
                concept_id_value=167,
                concept_id_description="descriptionB",
                concept_type="conceptTypeB",
                concept_id_type=selected_concept_id_type,
            ),
            AllergyDetail(
                concept_id_value=234,
                concept_id_description="descriptionC",
                concept_type="conceptTypeC",
                concept_id_type=exp_concept_id_type,
            ),
        ]
        # all good
        search_allergy.side_effect = [allergy_details]
        chatter.single_conversation.side_effect = [[{"conceptId": 167, "description": "descriptionB"}]]

        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = AllergyCommand(
            severity=AllergyCommand.Severity.MODERATE,
            narrative="theReaction",
            approximate_date=date(2025, 2, 4),
            allergy=Allergen(concept_id=167, concept_type=AllergenType(selected_concept_id_type)),
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected

        allergen_types = [AllergenType(1)]
        if exp_concept_id_type != 1:
            allergen_types.append(AllergenType(exp_concept_id_type))

        calls = [call(keywords, allergen_types)]
        assert search_allergy.mock_calls == calls
        calls = [call("167", "descriptionB")]
        assert add_code2description.mock_calls == calls
        calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
        assert chatter.mock_calls == calls
        reset_mocks()

        # no good response
        search_allergy.side_effect = [allergy_details]
        chatter.single_conversation.side_effect = [[]]

        result = tested.command_from_json(instruction, chatter)
        command = AllergyCommand(
            severity=AllergyCommand.Severity.MODERATE,
            narrative="theReaction",
            approximate_date=date(2025, 2, 4),
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected

        allergen_types = [AllergenType(1)]
        if exp_concept_id_type != 1:
            allergen_types.append(AllergenType(exp_concept_id_type))

        calls = [call(keywords, allergen_types)]
        assert search_allergy.mock_calls == calls
        assert add_code2description.mock_calls == []
        calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
        assert chatter.mock_calls == calls
        reset_mocks()

        # no allergies
        search_allergy.side_effect = [[]]
        chatter.single_conversation.side_effect = [[]]

        result = tested.command_from_json(instruction, chatter)
        command = AllergyCommand(
            severity=AllergyCommand.Severity.MODERATE,
            narrative="theReaction",
            approximate_date=date(2025, 2, 4),
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected

        allergen_types = [AllergenType(1)]
        if exp_concept_id_type != 1:
            allergen_types.append(AllergenType(exp_concept_id_type))

        calls = [call(keywords, allergen_types)]
        assert search_allergy.mock_calls == calls
        assert add_code2description.mock_calls == []
        assert chatter.mock_calls == []
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "",
        "type": "",
        "severity": "",
        "reaction": "",
        "approximateDateOfOnset": None,
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 1
    schema = schemas[0]

    #
    schema_hash = md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "d50901bfa8bdc4165d5fb42783be80f6"
    assert schema_hash == expected_hash

    tests = [
        (
            [
                {
                    "keywords": "peanuts,nuts",
                    "type": "allergy group",
                    "severity": "mild",
                    "reaction": "hives",
                    "approximateDateOfOnset": "2025-02-04",
                }
            ],
            "",
        ),
        (
            [
                {
                    "keywords": "NKA",
                    "type": "medication",
                    "severity": "moderate",
                    "reaction": "none",
                    "approximateDateOfOnset": None,
                }
            ],
            "",
        ),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "type": "allergy group",
                    "severity": "mild",
                    "reaction": "hives",
                    "approximateDateOfOnset": "2025-02-04",
                },
                {
                    "keywords": "penicillin",
                    "type": "medication",
                    "severity": "severe",
                    "reaction": "anaphylaxis",
                    "approximateDateOfOnset": "2020-01-01",
                },
            ],
            "[{'keywords': 'peanuts', "
            "'type': 'allergy group', "
            "'severity': 'mild', "
            "'reaction': 'hives', "
            "'approximateDateOfOnset': "
            "'2025-02-04'}, "
            "{'keywords': 'penicillin', "
            "'type': 'medication', "
            "'severity': 'severe', "
            "'reaction': 'anaphylaxis', "
            "'approximateDateOfOnset': '2020-01-01'}] is too long",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "type": "allergy group",
                    "severity": "mild",
                    "reaction": "hives",
                    "approximateDateOfOnset": "2025-02-04",
                    "extra": "field",
                }
            ],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        (
            [
                {
                    "type": "allergy group",
                    "severity": "mild",
                    "reaction": "hives",
                    "approximateDateOfOnset": "2025-02-04",
                }
            ],
            "'keywords' is a required property, in path [0]",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "severity": "mild",
                    "reaction": "hives",
                    "approximateDateOfOnset": "2025-02-04",
                }
            ],
            "'type' is a required property, in path [0]",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "type": "allergy group",
                    "reaction": "hives",
                    "approximateDateOfOnset": "2025-02-04",
                }
            ],
            "'severity' is a required property, in path [0]",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "type": "allergy group",
                    "severity": "mild",
                    "approximateDateOfOnset": "2025-02-04",
                }
            ],
            "'reaction' is a required property, in path [0]",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "type": "allergy group",
                    "severity": "mild",
                    "reaction": "hives",
                }
            ],
            "'approximateDateOfOnset' is a required property, in path [0]",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "type": "invalid_type",
                    "severity": "mild",
                    "reaction": "hives",
                    "approximateDateOfOnset": "2025-02-04",
                }
            ],
            "'invalid_type' is not one of ['allergy group', 'medication', 'ingredient'], in path [0, 'type']",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "type": "allergy group",
                    "severity": "mild",
                    "reaction": "hives",
                    "approximateDateOfOnset": "02-04-2025",
                }
            ],
            "'02-04-2025' does not match '^\\\\d{4}-\\\\d{2}-\\\\d{2}$', in path [0, 'approximateDateOfOnset']",
        ),
        (
            [
                {
                    "keywords": "peanuts",
                    "type": "allergy group",
                    "severity": "mild",
                    "reaction": "hives",
                    "approximateDateOfOnset": "10-21-89",
                }
            ],
            "'10-21-89' does not match '^\\\\d{4}-\\\\d{2}-\\\\d{2}$', in path [0, 'approximateDateOfOnset']",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Any diagnosed allergy, one instruction per allergy. "
        "There can be only one allergy per instruction, and no instruction in the lack of. "
        "But, if it is explicitly said that the patient has no known allergy, add an instruction mentioning it."
    )
    assert result == expected


@patch.object(LimitedCache, "current_allergies")
def test_instruction_constraints(current_allergies):
    def reset_mocks():
        current_allergies.reset_mock()

    tested = helper_instance()

    allergies = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (
            allergies,
            "Only document 'Allergy' for allergies outside the following list: display1a, display2a, display3a.",
        ),
        ([], ""),
    ]
    for side_effect, expected in tests:
        current_allergies.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_allergies.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
