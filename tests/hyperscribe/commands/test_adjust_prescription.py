from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands import AdjustPrescriptionCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.constants import ClinicalQuantity

from hyperscribe.commands.adjust_prescription import AdjustPrescription
from hyperscribe.commands.base_prescription import BasePrescription
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_cached import MedicationCached
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_detail_quantity import MedicationDetailQuantity
from hyperscribe.structures.medication_search import MedicationSearch
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> AdjustPrescription:
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
    return AdjustPrescription(settings, cache, identification)


def test_class():
    tested = AdjustPrescription
    assert issubclass(tested, BasePrescription)


def test_command_type():
    tested = AdjustPrescription
    result = tested.command_type()
    expected = "AdjustPrescriptionCommand"
    assert result == expected


def test_schema_key():
    tested = AdjustPrescription
    result = tested.schema_key()
    expected = "adjustPrescription"
    assert result == expected


def test_note_section():
    tested = AdjustPrescription
    result = tested.note_section()
    expected = "Plan"
    assert result == expected


def test_staged_command_extract():
    tested = AdjustPrescription
    tests = [
        ({}, None),
        (
            {
                "sig": "theSig",
                "refills": 2,
                "prescribe": {"text": "theOldMedication", "value": 292907},
                "change_medication_to": {"text": "theNewMedication", "value": 292911},
                "days_supply": 7,
                "indications": [{"text": "theIndication1"}, {"text": "theIndication2"}, {"text": "theIndication3"}],
                "substitutions": "allowed",
                "note_to_pharmacist": "theNoteToPharmacist",
                "quantity_to_dispense": "3",
            },
            CodedItem(
                label="theOldMedication to theNewMedication: theSig (dispense: 3, supply days: 7, refills: 2, "
                "substitution: allowed, related conditions: theIndication1/theIndication2/theIndication3)",
                code="292907",
                uuid="",
            ),
        ),
        (
            {
                "sig": "theSig",
                "refills": 2,
                "prescribe": {"text": "", "value": 292907},
                "days_supply": 7,
                "indications": [{"text": "theIndication1"}, {"text": "theIndication2"}, {"text": "theIndication3"}],
                "substitutions": "allowed",
                "note_to_pharmacist": "theNoteToPharmacist",
                "quantity_to_dispense": "3",
            },
            None,
        ),
        (
            {
                "sig": "",
                "refills": None,
                "prescribe": {"text": "theMedication", "value": None},
                "days_supply": None,
                "indications": [{"text": "theIndication1"}, {"text": "theIndication2"}, {"text": "theIndication3"}],
                "substitutions": None,
                "note_to_pharmacist": "theNoteToPharmacist",
                "quantity_to_dispense": None,
            },
            CodedItem(
                label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, "
                "related conditions: theIndication1/theIndication2/theIndication3)",
                code="",
                uuid="",
            ),
        ),
        (
            {
                "sig": "",
                "refills": None,
                "prescribe": {"text": "theMedication", "value": None},
                "days_supply": None,
                "indications": [],
                "substitutions": None,
                "note_to_pharmacist": "theNoteToPharmacist",
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
@patch.object(AdjustPrescription, "add_code2description")
@patch.object(AdjustPrescription, "set_medication_dosage")
@patch.object(AdjustPrescription, "medications_from")
@patch.object(LimitedCache, "current_conditions")
def test_command_from_json(
    current_conditions,
    medications_from,
    set_medication_dosage,
    add_code2description,
    current_medications,
):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        current_conditions.reset_mock()
        medications_from.reset_mock()
        set_medication_dosage.reset_mock()
        add_code2description.reset_mock()
        current_medications.reset_mock()

    tested = helper_instance()

    medication_record = MedicationDetail(
        fdb_code="code369",
        description="labelB",
        quantities=[
            MedicationDetailQuantity(
                quantity="7",
                representative_ndc="ndc1",
                ncpdp_quantity_qualifier_code="qualifier1",
                ncpdp_quantity_qualifier_description="description1",
            ),
            MedicationDetailQuantity(
                quantity="3",
                representative_ndc="ndc2",
                ncpdp_quantity_qualifier_code="qualifier2",
                ncpdp_quantity_qualifier_description="description2",
            ),
        ],
    )
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
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
    keywords = ["keyword1", "keyword2", "keyword3"]
    brands = ["brand1", "brand2", "brand3", "brand4"]

    # incorrect index
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[medication_record]]
    current_medications.side_effect = [medications]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "previous_information": "thePreviousInformation",
        "parameters": {
            "oldMedication": "display2a",
            "oldMedicationIndex": -1,
            "newMedication": {
                "keywords": "keyword1,keyword2,keyword3",
                "brandNames": "brand1,brand2,brand3,brand4",
                "sameAsCurrent": False,
            },
            "sig": "theSig",
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = AdjustPrescriptionCommand(
        sig="theSig",
        days_supply=11,
        substitutions=AdjustPrescriptionCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [
        call(
            instruction,
            chatter,
            MedicationSearch(comment="theComment", keywords=keywords, brand_names=brands, related_condition=""),
        ),
    ]
    assert medications_from.mock_calls == calls
    calls = [call(instruction, chatter, "theComment", command, medication_record)]
    assert set_medication_dosage.mock_calls == calls
    calls = [call("code369", "labelB")]
    assert add_code2description.mock_calls == calls
    assert current_medications.mock_calls == []
    assert chatter.mock_calls == []
    reset_mocks()

    # different medications
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[medication_record]]
    current_medications.side_effect = [medications]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "previous_information": "thePreviousInformation",
        "parameters": {
            "oldMedication": "display2a",
            "oldMedicationIndex": 1,
            "newMedication": {
                "keywords": "keyword1,keyword2,keyword3",
                "brandNames": "brand1,brand2,brand3,brand4",
                "sameAsCurrent": False,
            },
            "sig": "theSig",
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = AdjustPrescriptionCommand(
        fdb_code="fdb2",
        new_fdb_code="fdb2",
        type_to_dispense=ClinicalQuantity(representative_ndc="ndc2", ncpdp_quantity_qualifier_code="puc2"),
        sig="theSig",
        days_supply=11,
        substitutions=AdjustPrescriptionCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [
        call(
            instruction,
            chatter,
            MedicationSearch(comment="theComment", keywords=keywords, brand_names=brands, related_condition=""),
        ),
    ]
    assert medications_from.mock_calls == calls
    calls = [call(instruction, chatter, "theComment", command, medication_record)]
    assert set_medication_dosage.mock_calls == calls
    calls = [
        call("fdb2", "display2"),
        call("code369", "labelB"),
    ]
    assert add_code2description.mock_calls == calls
    calls = [call()]
    assert current_medications.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # same medications
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[medication_record]]
    current_medications.side_effect = [medications]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "previous_information": "thePreviousInformation",
        "parameters": {
            "oldMedication": "display2a",
            "oldMedicationIndex": 1,
            "newMedication": {
                "keywords": "keyword1,keyword2,keyword3",
                "brandNames": "brand1,brand2,brand3,brand4",
                "sameAsCurrent": True,
            },
            "sig": "theSig",
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = AdjustPrescriptionCommand(
        fdb_code="fdb2",
        new_fdb_code="fdb2",
        type_to_dispense=ClinicalQuantity(representative_ndc="ndc2", ncpdp_quantity_qualifier_code="puc2"),
        sig="theSig",
        days_supply=11,
        substitutions=AdjustPrescriptionCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert current_conditions.mock_calls == []
    assert medications_from.mock_calls == []
    assert set_medication_dosage.mock_calls == []
    calls = [call("fdb2", "display2")]
    assert add_code2description.mock_calls == calls
    calls = [call()]
    assert current_medications.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # no medication
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[]]
    current_medications.side_effect = [medications]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "previous_information": "thePreviousInformation",
        "parameters": {
            "oldMedication": "display2a",
            "oldMedicationIndex": 1,
            "newMedication": {
                "keywords": "keyword1,keyword2,keyword3",
                "brandNames": "brand1,brand2,brand3,brand4",
                "sameAsCurrent": False,
            },
            "sig": "theSig",
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = AdjustPrescriptionCommand(
        fdb_code="fdb2",
        new_fdb_code="fdb2",
        type_to_dispense=ClinicalQuantity(representative_ndc="ndc2", ncpdp_quantity_qualifier_code="puc2"),
        sig="theSig",
        days_supply=11,
        substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [
        call(
            instruction,
            chatter,
            MedicationSearch(comment="theComment", keywords=keywords, brand_names=brands, related_condition=""),
        ),
    ]
    assert medications_from.mock_calls == calls
    assert set_medication_dosage.mock_calls == []
    calls = [call()]
    assert current_medications.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


def test_command_parameters():
    tested = helper_instance()
    result = tested.command_parameters()
    expected = {
        "oldMedication": "",
        "oldMedicationIndex": -1,
        "newMedication": {
            "keywords": "",
            "brandNames": "",
            "sameAsCurrent": False,
        },
        "sig": "",
        "suppliedDays": 0,
        "substitution": "",
        "comment": "",
    }
    assert result == expected


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
                        "description": "Rationale of the change of prescription including all "
                        "important words, as free text",
                        "type": "string",
                    },
                    "newMedication": {
                        "additionalProperties": False,
                        "properties": {
                            "brandNames": {
                                "description": "Comma separated of known medication names related to the keywords",
                                "type": "string",
                            },
                            "keywords": {
                                "description": "Comma separated keywords of up to 5 synonyms of "
                                "the new medication to prescribe",
                                "type": "string",
                            },
                            "sameAsCurrent": {
                                "description": "Same medication as current one",
                                "type": "boolean",
                            },
                        },
                        "required": ["keywords", "brandNames", "sameAsCurrent"],
                        "type": "object",
                    },
                    "oldMedication": {
                        "description": "The current medication to be adjusted",
                        "enum": ["display1", "display2", "display3"],
                        "type": "string",
                    },
                    "oldMedicationIndex": {
                        "description": "Index of the medication to change",
                        "maximum": 2,
                        "minimum": 0,
                        "type": "integer",
                    },
                    "sig": {
                        "description": "Directions for the medication, as free text",
                        "type": "string",
                    },
                    "substitution": {
                        "description": "Substitution status for the prescription, default is 'allowed'",
                        "enum": ["allowed", "not_allowed"],
                        "type": "string",
                    },
                    "suppliedDays": {
                        "description": "Duration of the treatment in days, at least 1",
                        "exclusiveMinimum": 0,
                        "type": "integer",
                    },
                },
                "required": [
                    "oldMedication",
                    "oldMedicationIndex",
                    "newMedication",
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
        "Change the prescription of a current medication (display1, display2, display3), "
        "including the new medication, the directions, the duration and the dosage. "
        "There can be only one change of prescription per instruction, and no instruction in the lack of."
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
        "'AdjustPrescription' has to be related to one of the following medications: "
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
