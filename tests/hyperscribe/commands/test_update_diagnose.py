from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.update_diagnosis import UpdateDiagnosisCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.update_diagnose import UpdateDiagnose
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


def helper_instance() -> UpdateDiagnose:
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
    return UpdateDiagnose(settings, cache, identification)


def test_class():
    tested = UpdateDiagnose
    assert issubclass(tested, Base)


def test_schema_key():
    tested = UpdateDiagnose
    result = tested.schema_key()
    expected = "updateDiagnosis"
    assert result == expected


def test_note_section():
    tested = UpdateDiagnose
    result = tested.note_section()
    expected = "Assessment"
    assert result == expected


def test_staged_command_extract():
    tested = UpdateDiagnose
    tests = [
        ({}, None),
        (
            {
                "condition": {"text": "theCondition"},
                "narrative": "theNarrative",
                "background": "theBackground",
                "new_condition": {"text": "theNewCondition"},
            },
            CodedItem(label="theCondition to theNewCondition: theNarrative", code="", uuid=""),
        ),
        (
            {
                "condition": {"text": ""},
                "narrative": "theNarrative",
                "background": "theBackground",
                "new_condition": {"text": "theNewCondition"},
            },
            None,
        ),
        (
            {
                "condition": {"text": "theCondition"},
                "narrative": "",
                "background": "theBackground",
                "new_condition": {"text": "theNewCondition"},
            },
            CodedItem(label="theCondition to theNewCondition: n/a", code="", uuid=""),
        ),
        (
            {
                "condition": {"text": "theCondition"},
                "narrative": "theNarrative",
                "background": "theBackground",
                "new_condition": {"text": ""},
            },
            CodedItem(label="theCondition to n/a: theNarrative", code="", uuid=""),
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(CanvasScience, "search_conditions")
@patch.object(LimitedCache, "current_conditions")
@patch.object(UpdateDiagnose, "add_code2description")
def test_command_from_json(add_code2description, current_conditions, search_conditions):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        current_conditions.reset_mock()
        search_conditions.reset_mock()
        chatter.reset_mock()

    system_prompt = [
        "The conversation is in the medical context.",
        "",
        "Your task is to identify the most relevant condition diagnosed for a patient out of a list of conditions.",
        "",
    ]
    user_prompt = [
        "Here is the comment provided by the healthcare provider in regards to the diagnosis:",
        "```text",
        "keywords: keyword1,keyword2,keyword3",
        " -- ",
        "theRationale",
        "",
        "theAssessment",
        "```",
        "",
        "Among the following conditions, identify the most relevant one:",
        "",
        " * labelA (ICD-10: code12.3)\n * labelB (ICD-10: code36.9)\n * labelC (ICD-10: code75.2)",
        "",
        "Please, present your findings in a JSON format within a Markdown code block like:",
        "```json",
        '[{"ICD10": "the ICD-10 code", "label": "the label"}]',
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
                    "ICD10": {"type": "string", "minLength": 1},
                    "label": {"type": "string", "minLength": 1},
                },
                "required": ["ICD10", "label"],
                "additionalProperties": False,
            },
            "minItems": 1,
            "maxItems": 1,
        },
    ]
    keywords = ["keyword1", "keyword2", "keyword3", "ICD01", "ICD02", "ICD03"]
    tested = helper_instance()

    tests = [
        (1, "CODE45", [call("theUuid2", "display2a"), call("code369", "labelB")]),
        (2, "CODE9876", [call("theUuid3", "display3a"), call("code369", "labelB")]),
        (4, None, [call("code369", "labelB")]),
    ]
    for idx, exp_current_icd10, exp_calls in tests:
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
                "ICD10": "ICD01,ICD02,ICD03",
                "previousCondition": "theCondition",
                "previousConditionIndex": idx,
                "rationale": "theRationale",
                "assessment": "theAssessment",
            },
        }
        conditions = [
            CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
            CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
            CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
        ]
        search = [
            Icd10Condition(code="code123", label="labelA"),
            Icd10Condition(code="code369", label="labelB"),
            Icd10Condition(code="code752", label="labelC"),
        ]

        # all good
        current_conditions.side_effect = [conditions]
        search_conditions.side_effect = [search]
        chatter.single_conversation.side_effect = [[{"ICD10": "code369", "label": "labelB"}]]

        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = UpdateDiagnosisCommand(
            background="theRationale",
            narrative="theAssessment",
            note_uuid="noteUuid",
            new_condition_code="code369",
        )
        if exp_current_icd10:
            command.condition_code = exp_current_icd10
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected, f"---> {idx}"
        assert add_code2description.mock_calls == exp_calls
        calls = [call()]
        assert current_conditions.mock_calls == calls
        calls = [call(keywords)]
        assert search_conditions.mock_calls == calls
        calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
        assert chatter.mock_calls == calls
        reset_mocks()

        # no condition found
        exp_calls.pop()
        current_conditions.side_effect = [conditions]
        search_conditions.side_effect = [[]]
        chatter.single_conversation.side_effect = []

        result = tested.command_from_json(instruction, chatter)
        command = UpdateDiagnosisCommand(background="theRationale", narrative="theAssessment", note_uuid="noteUuid")
        if exp_current_icd10:
            command.condition_code = exp_current_icd10
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected, f"---> {idx}"
        assert add_code2description.mock_calls == exp_calls
        calls = [call()]
        assert current_conditions.mock_calls == calls
        calls = [call(keywords)]
        assert search_conditions.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()

        # no response
        current_conditions.side_effect = [conditions]
        search_conditions.side_effect = [search]
        chatter.single_conversation.side_effect = [[]]

        result = tested.command_from_json(instruction, chatter)
        command = UpdateDiagnosisCommand(background="theRationale", narrative="theAssessment", note_uuid="noteUuid")
        if exp_current_icd10:
            command.condition_code = exp_current_icd10
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected, f"---> {idx}"
        assert add_code2description.mock_calls == exp_calls
        calls = [call()]
        assert current_conditions.mock_calls == calls
        calls = [call(keywords)]
        assert search_conditions.mock_calls == calls
        calls = [call.single_conversation(system_prompt, user_prompt, schemas, instruction)]
        assert chatter.mock_calls == calls
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "keywords": "",
        "ICD10": "",
        "previousCondition": "",
        "previousConditionIndex": -1,
        "rationale": "",
        "assessment": "",
    }
    assert result == expected


@patch.object(LimitedCache, "current_conditions")
def test_command_parameters_schemas(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.command_parameters_schemas()
    expected = [
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "items": {
                "additionalProperties": False,
                "properties": {
                    "ICD10": {
                        "description": "Comma separated keywords of up to 5 ICD-10 codes of the "
                        "new diagnosed condition",
                        "type": "string",
                    },
                    "assessment": {
                        "description": "Today's assessment of the new condition, as free text",
                        "type": "string",
                    },
                    "keywords": {
                        "description": "Comma separated keywords of up to 5 synonyms of the new diagnosed condition",
                        "type": "string",
                    },
                    "previousCondition": {
                        "description": "The previous condition to be updated",
                        "enum": ["display1a", "display2a", "display3a"],
                        "type": "string",
                    },
                    "previousConditionIndex": {
                        "description": "Index of the previous Condition",
                        "maximum": 2,
                        "minimum": 0,
                        "type": "integer",
                    },
                    "rationale": {
                        "description": "Rationale about the current assessment, as free text",
                        "type": "string",
                    },
                },
                "required": [
                    "keywords",
                    "ICD10",
                    "previousCondition",
                    "previousConditionIndex",
                    "rationale",
                    "assessment",
                ],
                "type": "object",
            },
            "maxItems": 1,
            "minItems": 1,
            "type": "array",
        },
    ]
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_instruction_description(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_description()
    expected = (
        "Change of a medical condition (display1a, display2a, display3a) identified by the provider, "
        "including rationale, current assessment. "
        "There is one instruction per condition change, and no instruction in the lack of."
    )
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_instruction_constraints(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    current_conditions.side_effect = [conditions]
    result = tested.instruction_constraints()
    expected = (
        "'UpdateDiagnose' has to be an update from one of the following conditions: "
        "display1a (ICD-10: CODE12.3), "
        "display2a (ICD-10: CODE45), "
        "display3a (ICD-10: CODE98.76)"
    )
    assert result == expected
    calls = [call()]
    assert current_conditions.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_is_available(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [(conditions, True), ([], False)]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()
