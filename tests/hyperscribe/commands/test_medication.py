from hashlib import md5
import json
from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.medication_statement import MedicationStatementCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.medication import Medication
from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.llms.llm_base import LlmBase
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_cached import MedicationCached
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Medication:
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
    return Medication(settings, cache, identification)


def test_class():
    tested = Medication
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Medication
    result = tested.schema_key()
    expected = "medicationStatement"
    assert result == expected


def test_note_section():
    tested = Medication
    result = tested.note_section()
    expected = "History"
    assert result == expected


def test_staged_command_extract():
    tested = Medication
    tests = [
        ({}, None),
        (
            {"sig": "theSig", "medication": {"text": "theMedication"}},
            CodedItem(label="theMedication: theSig", code="", uuid=""),
        ),
        ({"sig": "theSig", "medication": {"text": ""}}, None),
        ({"sig": "", "medication": {"text": "theMedication"}}, CodedItem(label="theMedication: n/a", code="", uuid="")),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "medication_details")
@patch.object(Medication, "add_code2description")
def test_command_from_json(add_code2description, medication_details):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        medication_details.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant medication to prescribe to a patient out of a list of medications.",
        "",
    ]
    user_prompt = [
        "Here is the comment provided by the healthcare provider in regards to the prescription:",
        "```text",
        "keywords: keyword1,keyword2,keyword3",
        " -- ",
        "theSig",
        "```",
        "",
        "Among the following medications, identify the most relevant one:",
        "",
        " * labelA (fdbCode: code123)\n * labelB (fdbCode: code369)\n * labelC (fdbCode: code752)",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"fdbCode": "the fdb code, as int", "description": "the description"}]',
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
                    "fdbCode": {"type": "integer", "minimum": 1},
                    "description": {"type": "string", "minLength": 1},
                },
                "required": ["fdbCode", "description"],
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
        "parameters": {"keywords": "keyword1,keyword2,keyword3", "sig": "theSig"},
    }
    medications = [
        MedicationDetail(fdb_code="code123", description="labelA", quantities=[]),
        MedicationDetail(fdb_code="code369", description="labelB", quantities=[]),
        MedicationDetail(fdb_code="code752", description="labelC", quantities=[]),
    ]

    # all good
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[{"fdbCode": "code369", "description": "labelB"}]]

    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = MedicationStatementCommand(sig="theSig", fdb_code="code369", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = [call("code369", "labelB")]
    assert add_code2description.mock_calls == calls
    calls = [call(keywords)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no good response
    medication_details.side_effect = [medications]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = MedicationStatementCommand(sig="theSig", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert add_code2description.mock_calls == []
    calls = [call(keywords)]
    assert medication_details.mock_calls == calls
    calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
    assert chatter.mock_calls == calls
    reset_mocks()

    # no medical concept
    medication_details.side_effect = [[]]
    chatter.single_conversation.side_effect = [[]]

    result = tested.command_from_json(instruction, chatter)
    command = MedicationStatementCommand(sig="theSig", note_uuid="noteUuid")
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert add_code2description.mock_calls == []
    calls = [call(keywords)]
    assert medication_details.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "",
        "sig": "",
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    schemas = tested.command_parameters_schemas()
    assert len(schemas) == 1
    schema = schemas[0]

    #
    schema_hash = md5(json.dumps(schema, sort_keys=True).encode()).hexdigest()
    expected_hash = "f93a9337b80f990ef0f4d19240e24f03"
    assert schema_hash == expected_hash

    tests = [
        (
            [{"keywords": "aspirin,pain reliever", "sig": "Take 1 tablet daily"}],
            "",
        ),
        (
            [],
            "[] should be non-empty",
        ),
        (
            [
                {"keywords": "aspirin", "sig": "Take 1 tablet daily"},
                {"keywords": "ibuprofen", "sig": "Take as needed"},
            ],
            "[{'keywords': 'aspirin', 'sig': 'Take 1 tablet daily'}, "
            "{'keywords': 'ibuprofen', 'sig': 'Take as needed'}] is too long",
        ),
        (
            [{"keywords": "aspirin", "sig": "Take 1 tablet daily", "extra": "field"}],
            "Additional properties are not allowed ('extra' was unexpected), in path [0]",
        ),
        (
            [{"sig": "Take 1 tablet daily"}],
            "'keywords' is a required property, in path [0]",
        ),
        (
            [{"keywords": "aspirin"}],
            "'sig' is a required property, in path [0]",
        ),
    ]
    for idx, (dictionary, expected) in enumerate(tests):
        result = LlmBase.json_validator(dictionary, schema)
        assert result == expected, f"---> {idx}"


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Current medication being consumed by the patient, not a new prescription order. "
        "There can be only one medication per instruction, and no instruction in the lack of."
    )
    assert result == expected


@patch.object(LimitedCache, "current_medications")
def test_instruction_constraints(current_medications):
    def reset_mocks():
        current_medications.reset_mock()

    tested = helper_instance()

    medications = [
        MedicationCached(
            uuid="theUuid",
            label="display1",
            code_rx_norm="rxNorm1",
            code_fdb="fdb1",
            national_drug_code="ndc1",
            potency_unit_code="puc1",
        ),
        MedicationCached(
            uuid="theUuid2",
            label="display2",
            code_rx_norm="rxNorm2",
            code_fdb="fdb2",
            national_drug_code="ndc2",
            potency_unit_code="puc2",
        ),
        MedicationCached(
            uuid="theUuid3",
            label="display3",
            code_rx_norm="rxNorm3",
            code_fdb="fdb3",
            national_drug_code="ndc3",
            potency_unit_code="puc3",
        ),
    ]
    tests = [
        (
            medications,
            "Only document 'Medication' for medications outside the following list: display1, display2, display3.",
        ),
        ([], ""),
    ]
    for side_effect, expected in tests:
        current_medications.side_effect = [side_effect]
        result = tested.instruction_constraints()
        assert result == expected
        calls = [call()]
        assert current_medications.mock_calls == calls
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
