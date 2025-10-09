from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.prescribe import PrescribeCommand

from hyperscribe.commands.base_prescription import BasePrescription
from hyperscribe.commands.prescription import Prescription
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_detail_quantity import MedicationDetailQuantity
from hyperscribe.structures.medication_search import MedicationSearch
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Prescription:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
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
    return Prescription(settings, cache, identification)


def test_class():
    tested = Prescription
    assert issubclass(tested, BasePrescription)


def test_schema_key():
    tested = Prescription
    result = tested.schema_key()
    expected = "prescribe"
    assert result == expected


def test_staged_command_extract():
    tested = Prescription
    tests = [
        ({}, None),
        (
            {
                "sig": "theSig",
                "refills": 2,
                "prescribe": {"text": "theMedication", "value": 292907},
                "days_supply": 7,
                "indications": [
                    {"text": "theIndication1"},
                    {"text": "theIndication2"},
                    {"text": "theIndication3"},
                ],
                "substitutions": "allowed",
                "note_to_pharmacist": "theNoteToPharmacist",
                "quantity_to_dispense": "3",
            },
            CodedItem(
                label="theMedication: theSig (dispense: 3, supply days: 7, refills: 2, substitution: allowed, "
                "related conditions: theIndication1/theIndication2/theIndication3)",
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


@patch.object(Prescription, "add_code2description")
@patch.object(Prescription, "set_medication_dosage")
@patch.object(Prescription, "medications_from")
@patch.object(LimitedCache, "current_conditions")
def test_command_from_json(current_conditions, medications_from, set_medication_dosage, add_code2description):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        current_conditions.reset_mock()
        medications_from.reset_mock()
        set_medication_dosage.reset_mock()
        add_code2description.reset_mock()

    tested = helper_instance()

    medication = MedicationDetail(
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
    keywords = ["keyword1", "keyword2", "keyword3"]
    brands = ["brand1", "brand2", "brand3", "brand4"]

    # with condition
    tests = [
        (1, "display2a", ["CODE45"], [call(), call()], [call("CODE45", "display2a"), call("code369", "labelB")]),
        (2, "display3a", ["CODE9876"], [call(), call()], [call("CODE98.76", "display3a"), call("code369", "labelB")]),
        (4, "", [], [call()], [call("code369", "labelB")]),
    ]
    for idx, condition_label, condition_icd10, condition_calls, exp_calls in tests:
        current_conditions.side_effect = [conditions, conditions]
        medications_from.side_effect = [[medication]]

        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                "keywords": "keyword1,keyword2,keyword3",
                "medicationNames": "brand1,brand2,brand3,brand4",
                "sig": "theSig",
                "suppliedDays": 11,
                "substitution": "not_allowed",
                "comment": "theComment",
                "condition": "theCondition",
                "conditionIndex": idx,
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = PrescribeCommand(
            sig="theSig",
            days_supply=11,
            substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
            prescriber_id="providerUuid",
            note_uuid="noteUuid",
        )
        if condition_icd10:
            command.icd10_codes = condition_icd10
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected, f"----> {idx}"
        assert current_conditions.mock_calls == condition_calls
        calls = [
            call(
                instruction,
                chatter,
                MedicationSearch(
                    comment="theComment",
                    keywords=keywords,
                    brand_names=brands,
                    related_condition=condition_label,
                ),
            ),
        ]
        assert medications_from.mock_calls == calls
        calls = [call(instruction, chatter, "theComment", command, medication)]
        assert set_medication_dosage.mock_calls == calls
        assert add_code2description.mock_calls == exp_calls
        assert chatter.mock_calls == []
        reset_mocks()

    # no condition
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[medication]]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "keywords": "keyword1,keyword2,keyword3",
            "medicationNames": "brand1,brand2,brand3,brand4",
            "sig": "theSig",
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = PrescribeCommand(
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
    calls = [call(instruction, chatter, "theComment", command, medication)]
    assert set_medication_dosage.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # no medication
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[]]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            "keywords": "keyword1,keyword2,keyword3",
            "medicationNames": "brand1,brand2,brand3,brand4",
            "sig": "theSig",
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = PrescribeCommand(
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
    assert chatter.mock_calls == []
    reset_mocks()


@patch.object(LimitedCache, "current_conditions")
def test_command_parameters(current_conditions):
    def reset_mocks():
        current_conditions.reset_mock()

    tested = helper_instance()

    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    tests = [
        (
            conditions,
            {
                "keywords": "comma separated list of up to 5 relevant drugs to consider prescribing",
                "medicationNames": "comma separated list of known medication names, generics and brands, related to "
                "the keywords",
                "sig": "directions as stated; if specific frequency mentioned (e.g. 'once weekly', 'twice daily'), "
                "preserve it exactly, as free text",
                "suppliedDays": "mandatory, duration of the treatment in days either as mentioned, or following the "
                "standard practices, as integer",
                "substitution": "one of: allowed/not_allowed",
                "comment": "rationale of the prescription including all mentioned details: medication name/brand, "
                "specific strength if stated (e.g. '2.5 mg', '10 mg'), route, and specific frequency if stated "
                "(e.g. 'once weekly', 'twice daily'), as free text",
                "condition": "None or, one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)",
                "conditionIndex": "index of the condition for which the medication is prescribed, as integer or -1 "
                "if the prescription is not related to any listed condition",
            },
        ),
        (
            [],
            {
                "keywords": "comma separated list of up to 5 relevant drugs to consider prescribing",
                "medicationNames": "comma separated list of known medication names, generics and brands, "
                "related to the keywords",
                "sig": "directions as stated; if specific frequency mentioned (e.g. 'once weekly', 'twice daily'), "
                "preserve it exactly, as free text",
                "suppliedDays": "mandatory, duration of the treatment in days either as mentioned, or following "
                "the standard practices, as integer",
                "substitution": "one of: allowed/not_allowed",
                "comment": "rationale of the prescription including all mentioned details: medication name/brand, "
                "specific strength if stated (e.g. '2.5 mg', '10 mg'), route, and specific frequency if stated "
                "(e.g. 'once weekly', 'twice daily'), as free text",
            },
        ),
    ]
    for side_effect, expected in tests:
        current_conditions.side_effect = [side_effect]
        result = tested.command_parameters()
        assert result == expected
        calls = [call()]
        assert current_conditions.mock_calls == calls
        reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Medication prescription, including the directions, the duration, the targeted condition and the dosage. "
        "Create as many instructions as necessary as there can be only one prescribed item per instruction, "
        "and no instruction in the lack of."
    )
    assert result == expected


def test_instruction_constraints():
    tested = helper_instance()
    result = tested.instruction_constraints()
    expected = '"Prescription" supports only one prescribed item per instruction.'
    assert result == expected


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
