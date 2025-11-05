from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.commands.refill import RefillCommand
from canvas_sdk.commands.constants import ClinicalQuantity

from hyperscribe.commands.base import Base
from hyperscribe.commands.refill import Refill
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_cached import MedicationCached
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Refill:
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
    return Refill(settings, cache, identification)


def test_class():
    tested = Refill
    assert issubclass(tested, Base)


def test_schema_key():
    tested = Refill
    result = tested.schema_key()
    expected = "refill"
    assert result == expected


def test_note_section():
    tested = Refill
    result = tested.note_section()
    expected = "Plan"
    assert result == expected


def test_staged_command_extract():
    tested = Refill
    tests = [
        ({}, None),
        (
            {
                "sig": "theSig",
                "refills": 2,
                "prescribe": {"text": "theMedication", "value": 292907},
                "days_supply": 90,
                "indications": [{"text": "theIndication1"}, {"text": "theIndication2"}, {"text": "theIndication3"}],
                "substitutions": "allowed",
                "note_to_pharmacist": "noteToPharmacist",
                "quantity_to_dispense": "30",
            },
            CodedItem(
                label="theMedication: theSig (dispense: 30, supply days: 90, refills: 2, substitution: "
                "allowed, related conditions: theIndication1/theIndication2/theIndication3)",
                code="",
                uuid="",
            ),
        ),
        (
            {
                "sig": "theSig",
                "refills": 2,
                "prescribe": {"text": "", "value": 292907},
                "days_supply": 90,
                "indications": [{"text": "theIndication1"}, {"text": "theIndication2"}, {"text": "theIndication3"}],
                "substitutions": "allowed",
                "note_to_pharmacist": "noteToPharmacist",
                "quantity_to_dispense": "30",
            },
            None,
        ),
        (
            {
                "sig": "",
                "refills": None,
                "prescribe": {"text": "theMedication", "value": 292907},
                "days_supply": None,
                "indications": [],
                "substitutions": None,
                "note_to_pharmacist": "noteToPharmacist",
                "quantity_to_dispense": None,
            },
            CodedItem(
                label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, "
                "related conditions: n/a)",
                code="",
                uuid="",
            ),
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "current_medications")
@patch.object(Refill, "add_code2description")
def test_command_from_json(add_code2description, current_medications):
    chatter = MagicMock()

    def reset_mocks():
        add_code2description.reset_mock()
        current_medications.reset_mock()
        chatter.reset_mock()

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
        (1, "fdb2", "ndc2", "puc2", [call("fdb2", "display2")]),
        (2, "fdb3", "ndc3", "puc3", [call("fdb3", "display3")]),
    ]
    for idx, code_fdb, national_drug_code, potency_unit_code, exp_calls in tests:
        current_medications.side_effect = [medications, medications]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "comment": "theComment",
                "medication": "display2",
                "medicationIndex": idx,
                "sig": "theSig",
                "substitution": "not_allowed",
                "suppliedDays": 7,
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = RefillCommand(
            fdb_code=code_fdb,
            sig="theSig",
            days_supply=7,
            type_to_dispense=ClinicalQuantity(
                representative_ndc=national_drug_code,
                ncpdp_quantity_qualifier_code=potency_unit_code,
            ),
            substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
            prescriber_id="providerUuid",
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        assert add_code2description.mock_calls == exp_calls
        calls = [call()]
        assert current_medications.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()
    #
    current_medications.side_effect = [medications]
    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "comment": "theComment",
            "medication": "display2",
            "medicationIndex": 4,
            "sig": "theSig",
            "substitution": "allowed",
            "suppliedDays": 7,
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = RefillCommand(
        sig="theSig",
        days_supply=7,
        substitutions=PrescribeCommand.Substitutions.ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    calls = []
    assert add_code2description.mock_calls == calls
    calls = [call()]
    assert current_medications.mock_calls == calls
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "medication": "",
        "medicationIndex": -1,
        "sig": "",
        "suppliedDays": 0,
        "substitution": "",
        "comment": "",
    }


@patch.object(LimitedCache, "current_medications")
def test_command_parameters_schemas(current_medications):
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
            potency_unit_code="puc4",
        ),
    ]
    current_medications.side_effect = [medications]
    result = tested.command_parameters_schemas()
    expected = [
        {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "items": {
                "additionalProperties": False,
                "properties": {
                    "comment": {
                        "description": "Rationale of the prescription, as free text",
                        "type": "string",
                    },
                    "medication": {
                        "description": "The medication to refill",
                        "enum": ["display1", "display2", "display3"],
                        "type": "string",
                    },
                    "medicationIndex": {
                        "description": "Index of the medication to refill",
                        "type": "integer",
                    },
                    "sig": {
                        "description": "Directions, as free text",
                        "type": "string",
                    },
                    "substitution": {
                        "description": "Substitution status for the refill",
                        "enum": ["allowed", "not_allowed"],
                        "type": "string",
                    },
                    "suppliedDays": {
                        "description": "Duration of the treatment in days",
                        "type": "integer",
                    },
                },
                "required": [
                    "medication",
                    "medicationIndex",
                    "sig",
                    "suppliedDays",
                    "substitution",
                    "comment",
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
    assert current_medications.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_medications")
def test_instruction_description(current_medications):
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
            potency_unit_code="puc4",
        ),
    ]
    current_medications.side_effect = [medications]
    result = tested.instruction_description()
    expected = (
        "Refill of a current medication (display1, display2, display3), "
        "including the directions, the duration, the targeted condition and the dosage. "
        "Only create when a refill is ordered during this visit, not when discussing refills already sent. "
        "There can be only one refill per instruction, and no instruction in the lack of."
    )
    assert result == expected
    calls = [call()]
    assert current_medications.mock_calls == calls
    reset_mocks()


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
            potency_unit_code="puc4",
        ),
    ]
    current_medications.side_effect = [medications]
    result = tested.instruction_constraints()
    expected = (
        "'Refill' has to be related to one of the following medications: "
        "display1 (RxNorm: rxNorm1), "
        "display2 (RxNorm: rxNorm2), "
        "display3 (RxNorm: rxNorm3)"
    )
    assert result == expected
    calls = [call()]
    assert current_medications.mock_calls == calls
    reset_mocks()


@patch.object(LimitedCache, "current_medications")
def test_is_available(current_medications):
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
            potency_unit_code="puc4",
        ),
    ]
    tests = [(medications, True), ([], False)]
    for side_effect, expected in tests:
        current_medications.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_medications.mock_calls == calls
        reset_mocks()
