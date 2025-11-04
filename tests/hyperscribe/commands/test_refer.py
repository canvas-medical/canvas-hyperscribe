from unittest.mock import MagicMock, patch, call

from canvas_sdk.commands import ReferCommand
from canvas_sdk.commands.constants import ServiceProvider

from hyperscribe.commands.base import Base
from hyperscribe.commands.refer import Refer
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.selector_chat import SelectorChat
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Refer:
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
    return Refer(settings, cache, identification)


def test_class():
    tested = Refer
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Refer
    result = tested.schema_key()
    expected = "refer"
    assert result == expected


def test_note_section():
    tested = Refer
    result = tested.note_section()
    expected = "Plan"
    assert result == expected


def test_staged_command_extract():
    tested = Refer
    tests = [
        ({}, None),
        (
            {
                "priority": "Urgent",
                "refer_to": {"text": "theReferred"},
                "indications": [{"text": "Indication1"}, {"text": "Indication2"}, {"text": "Indication3"}],
                "internal_comment": "theComment",
                "clinical_question": "theClinicalQuestion",
                "notes_to_specialist": "theNote",
                "documents_to_include": [{"text": "Document1"}, {"text": "Document2"}, {"text": "Document3"}],
            },
            CodedItem(
                label="referred to theReferred: theNote "
                "(priority: Urgent, question: theClinicalQuestion, "
                "documents: Document1/Document2/Document3, "
                "related conditions: Indication1/Indication2/Indication3)",
                code="",
                uuid="",
            ),
        ),
        (
            {"refer_to": {"text": "theReferred"}},
            CodedItem(
                label="referred to theReferred: n/a (priority: n/a, question: n/a, documents: n/a, "
                "related conditions: n/a)",
                code="",
                uuid="",
            ),
        ),
        (
            {
                "priority": "Urgent",
                "refer_to": {"text": ""},
                "indications": [{"text": "Indication1"}, {"text": "Indication2"}, {"text": "Indication3"}],
                "internal_comment": "theComment",
                "clinical_question": "theClinicalQuestion",
                "notes_to_specialist": "theNote",
                "documents_to_include": [{"text": "Document1"}, {"text": "Document2"}, {"text": "Document3"}],
            },
            None,
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "practice_setting")
@patch.object(SelectorChat, "contact_from")
@patch.object(SelectorChat, "condition_from")
@patch.object(Refer, "add_code2description")
def test_command_from_json(add_code2description, condition_from, contact_from, practice_setting):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        condition_from.reset_mock()
        contact_from.reset_mock()
        practice_setting.reset_mock()
        chatter.reset_mock()

    service_provider = ServiceProvider(
        first_name="theFirstName",
        last_name="theLastName",
        specialty="theSpecialty",
        practice_name="thePracticeName",
        business_address="theBusinessAddress",
    )

    tested = helper_instance()

    tests = [("", "theSpecialty"), ("some names", "theSpecialty some names")]
    for names, exp_contact_call in tests:
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "referredServiceProvider": {"names": names, "specialty": "theSpecialty"},
                "clinicalQuestion": "Diagnostic Uncertainty",
                "priority": "Routine",
                "notesToSpecialist": "theNoteToTheSpecialist",
                "comment": "theComment",
                "conditions": [
                    {"conditionKeywords": "condition1,condition2", "ICD10": "icd1,icd2"},
                    {"conditionKeywords": "condition3", "ICD10": "icd3"},
                    {"conditionKeywords": "condition4", "ICD10": "icd4"},
                ],
            },
        }
        command = ReferCommand(
            service_provider=service_provider,
            clinical_question=ReferCommand.ClinicalQuestion.DIAGNOSTIC_UNCERTAINTY,
            priority=ReferCommand.Priority.ROUTINE,
            notes_to_specialist="theNoteToTheSpecialist",
            comment="theComment",
            note_uuid="noteUuid",
            diagnosis_codes=["icd1", "icd3"],
        )
        condition_from.side_effect = [
            CodedItem(uuid="uuid1", label="condition1", code="icd1"),
            CodedItem(uuid="uuid3", label="condition3", code=""),
            CodedItem(uuid="uuid4", label="condition4", code="icd3"),
        ]
        contact_from.side_effect = [service_provider]
        practice_setting.side_effect = ["thePreferredLab"]

        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected

        calls = [
            call("icd1", "condition1"),
            call("icd3", "condition4"),
        ]
        assert add_code2description.mock_calls == calls
        calls = [
            call(instruction, chatter, ["condition1", "condition2"], ["icd1", "icd2"], "theComment"),
            call(instruction, chatter, ["condition3"], ["icd3"], "theComment"),
            call(instruction, chatter, ["condition4"], ["icd4"], "theComment"),
        ]
        assert condition_from.mock_calls == calls
        calls = [call(instruction, chatter, exp_contact_call, "thePreferredLab")]
        assert contact_from.mock_calls == calls
        calls = [call("serviceAreaZipCodes")]
        assert practice_setting.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "referredServiceProvider": {"specialty": "", "names": ""},
        "clinicalQuestion": "",
        "priority": "",
        "notesToSpecialist": "",
        "comment": "",
        "conditions": [],
    }
    assert result == expected


def test_command_parameters_schemas():
    tested = helper_instance()
    result = tested.command_parameters_schemas()
    expected = [
        {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "referredServiceProvider": {
                        "type": "object",
                        "properties": {
                            "specialty": {
                                "type": "string",
                                "description": "the specialty of the referred provider, required",
                            },
                            "names": {
                                "type": "string",
                                "description": "the names of the practice and/or of the referred provider, or empty",
                            },
                        },
                        "required": ["specialty", "names"],
                    },
                    "clinicalQuestion": {
                        "type": "string",
                        "enum": [
                            "Cognitive Assistance (Advice/Guidance)",
                            "Assistance with Ongoing Management",
                            "Specialized intervention",
                            "Diagnostic Uncertainty",
                        ],
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["Routine", "Urgent"],
                    },
                    "notesToSpecialist": {
                        "type": "string",
                        "description": "note or question to be sent to the referred specialist, "
                        "concise, directly derived from the transcript content and required",
                    },
                    "comment": {
                        "type": "string",
                        "description": "Direct clinical reasoning statement, derived only from transcript "
                        "content. Express the medical findings and purpose of the referral "
                        "as a concise clinical note, without introducing phrases like "
                        "'referral' or 'rationale'.",
                    },
                    "conditions": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "conditionKeywords": {
                                    "type": "string",
                                    "description": "Comma-separated keywords to find in a database "
                                    "(using OR criteria) the condition related to the referral.",
                                },
                                "ICD10": {
                                    "type": "string",
                                    "description": "Comma-separated ICD-10 codes (up to 5) for the condition "
                                    "related to the referral.",
                                },
                            },
                            "required": ["conditionKeywords", "ICD10"],
                        },
                    },
                },
                "required": [
                    "referredServiceProvider",
                    "clinicalQuestion",
                    "priority",
                    "notesToSpecialist",
                    "comment",
                    "conditions",
                ],
            },
        }
    ]
    assert result == expected


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Referral to a specialist, including the rationale and the targeted conditions. "
        "There can be one and only one referral in an instruction with all necessary information, "
        "and no instruction in the lack of."
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
