from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands import AdjustPrescriptionCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.constants import ClinicalQuantity
from canvas_sdk.v1.data import Medication, MedicationCoding

from hyperscribe.commands.adjust_prescription import AdjustPrescription
from hyperscribe.commands.base_prescription import BasePrescription
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


def helper_instance() -> AdjustPrescription:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
    )
    cache = LimitedCache("patientUuid", {})
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


def test_schema_key():
    tested = AdjustPrescription
    result = tested.schema_key()
    expected = "adjustPrescription"
    assert result == expected


def test_staged_command_extract():
    tested = AdjustPrescription
    tests = [
        ({}, None),
        ({
             "sig": "theSig",
             "refills": 2,
             "prescribe": {
                 "text": "theOldMedication",
                 "value": 292907,
             },
             "change_medication_to": {
                 "text": "theNewMedication",
                 "value": 292911,
             },
             "days_supply": 7,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": "allowed",
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": "3"
         }, CodedItem(
            label="theOldMedication to theNewMedication: theSig (dispense: 3, supply days: 7, refills: 2, substitution: allowed, related conditions: theIndication1/theIndication2/theIndication3)",
            code="292907",
            uuid="",
        )),
        ({
             "sig": "theSig",
             "refills": 2,
             "prescribe": {
                 "text": "",
                 "value": 292907,
             },
             "days_supply": 7,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": "allowed",
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": "3"
         }, None),
        ({
             "sig": "",
             "refills": None,
             "prescribe": {
                 "text": "theMedication",
                 "value": None,
             },
             "days_supply": None,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": None,
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": None
         }, CodedItem(
            label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, related conditions: theIndication1/theIndication2/theIndication3)",
            code="",
            uuid="",
        )),
        ({
             "sig": "",
             "refills": None,
             "prescribe": {
                 "text": "theMedication",
                 "value": None,
             },
             "days_supply": None,
             "indications": [],
             "substitutions": None,
             "note_to_pharmacist": "theNoteToPharmacist",
             "quantity_to_dispense": None
         }, CodedItem(
            label="theMedication: n/a (dispense: n/a, supply days: n/a, refills: n/a, substitution: n/a, related conditions: n/a)",
            code="",
            uuid="",
        )),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(Medication, 'codings')
@patch.object(Medication, 'objects')
@patch.object(LimitedCache, "current_medications")
@patch.object(AdjustPrescription, "set_medication_dosage")
@patch.object(AdjustPrescription, "medications_from")
@patch.object(LimitedCache, "current_conditions")
def test_command_from_json(current_conditions, medications_from, set_medication_dosage, current_medications, medication_db, codings_db):
    chatter = MagicMock()

    def reset_mocks():
        chatter.reset_mock()
        current_conditions.reset_mock()
        medications_from.reset_mock()
        set_medication_dosage.reset_mock()
        current_medications.reset_mock()
        medication_db.reset_mock()
        codings_db.reset_mock()

    tested = helper_instance()

    medication_record = MedicationDetail(fdb_code="code369", description="labelB", quantities=[
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
    ])
    conditions = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE12.3"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE98.76"),
    ]
    medications = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    keywords = ["keyword1", "keyword2", "keyword3"]
    brands = ["brand1", "brand2", "brand3", "brand4"]

    # incorrect index
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[medication_record]]
    current_medications.side_effect = [medications]
    medication_db.get.side_effect = [Medication(national_drug_code="theNdc", potency_unit_code="thePuc")]
    codings_db.filter.return_value.first.side_effect = [MedicationCoding(system="theSystem", display="theDisplay", code="theCode"), ]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            'oldMedication': 'display2a',
            'oldMedicationIndex': -1,
            "newMedication": {
                "keywords": "keyword1,keyword2,keyword3",
                "brandNames": "brand1,brand2,brand3,brand4",
                "sameAsCurrent": False,
            },
            'sig': 'theSig',
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
    calls = [call(instruction, chatter, MedicationSearch(comment='theComment', keywords=keywords, brand_names=brands, related_condition=''))]
    assert medications_from.mock_calls == calls
    calls = [call(instruction, chatter, "theComment", command, medication_record)]
    assert set_medication_dosage.mock_calls == calls
    assert current_medications.mock_calls == []
    assert medication_db.mock_calls == []
    assert codings_db.mock_calls == []
    assert chatter.mock_calls == []
    reset_mocks()

    # different medications
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[medication_record]]
    current_medications.side_effect = [medications]
    medication_db.get.side_effect = [Medication(national_drug_code="theNdc", potency_unit_code="thePuc")]
    codings_db.filter.return_value.first.side_effect = [MedicationCoding(system="theSystem", display="theDisplay", code="theCode"), ]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            'oldMedication': 'display2a',
            'oldMedicationIndex': 1,
            "newMedication": {
                "keywords": "keyword1,keyword2,keyword3",
                "brandNames": "brand1,brand2,brand3,brand4",
                "sameAsCurrent": False,
            },
            'sig': 'theSig',
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = AdjustPrescriptionCommand(
        fdb_code='theCode',
        new_fdb_code='theCode',
        type_to_dispense=ClinicalQuantity(
            representative_ndc='theNdc',
            ncpdp_quantity_qualifier_code='thePuc',
        ),
        sig="theSig",
        days_supply=11,
        substitutions=AdjustPrescriptionCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [call(instruction, chatter, MedicationSearch(comment='theComment', keywords=keywords, brand_names=brands, related_condition=''))]
    assert medications_from.mock_calls == calls
    calls = [call(instruction, chatter, "theComment", command, medication_record)]
    assert set_medication_dosage.mock_calls == calls
    calls = [call()]
    assert current_medications.mock_calls == calls
    calls = [call.get(id='theUuid2')]
    assert medication_db.mock_calls == calls
    calls = [
        call.filter(system='http://www.fdbhealth.com/'),
        call.filter().first(),
    ]
    assert codings_db.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # same medications
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[medication_record]]
    current_medications.side_effect = [medications]
    medication_db.get.side_effect = [Medication(national_drug_code="theNdc", potency_unit_code="thePuc")]
    codings_db.filter.return_value.first.side_effect = [MedicationCoding(system="theSystem", display="theDisplay", code="theCode"), ]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            'oldMedication': 'display2a',
            'oldMedicationIndex': 1,
            "newMedication": {
                "keywords": "keyword1,keyword2,keyword3",
                "brandNames": "brand1,brand2,brand3,brand4",
                "sameAsCurrent": True,
            },
            'sig': 'theSig',
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = AdjustPrescriptionCommand(
        fdb_code='theCode',
        new_fdb_code='theCode',
        type_to_dispense=ClinicalQuantity(
            representative_ndc='theNdc',
            ncpdp_quantity_qualifier_code='thePuc',
        ),
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
    calls = [call()]
    assert current_medications.mock_calls == calls
    calls = [call.get(id='theUuid2')]
    assert medication_db.mock_calls == calls
    calls = [
        call.filter(system='http://www.fdbhealth.com/'),
        call.filter().first(),
    ]
    assert codings_db.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()

    # no medication
    current_conditions.side_effect = [conditions, conditions]
    medications_from.side_effect = [[]]
    current_medications.side_effect = [medications]
    medication_db.get.side_effect = [Medication(national_drug_code="theNdc", potency_unit_code="thePuc")]
    codings_db.filter.return_value.first.side_effect = [MedicationCoding(system="theSystem", display="theDisplay", code="theCode"), ]

    arguments = {
        "uuid": "theUuid",
        "index": 7,
        "instruction": "theInstruction",
        "information": "theInformation",
        "is_new": False,
        "is_updated": True,
        "parameters": {
            'oldMedication': 'display2a',
            'oldMedicationIndex': 1,
            "newMedication": {
                "keywords": "keyword1,keyword2,keyword3",
                "brandNames": "brand1,brand2,brand3,brand4",
                "sameAsCurrent": False,
            },
            'sig': 'theSig',
            "suppliedDays": 11,
            "substitution": "not_allowed",
            "comment": "theComment",
        },
    }
    instruction = InstructionWithParameters(**arguments)
    result = tested.command_from_json(instruction, chatter)
    command = AdjustPrescriptionCommand(
        fdb_code='theCode',
        new_fdb_code='theCode',
        type_to_dispense=ClinicalQuantity(
            representative_ndc='theNdc',
            ncpdp_quantity_qualifier_code='thePuc',
        ),
        sig="theSig",
        days_supply=11,
        substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
        prescriber_id="providerUuid",
        note_uuid="noteUuid",
    )
    expected = InstructionWithCommand(**(arguments | {"command": command}))
    assert result == expected
    assert current_conditions.mock_calls == []
    calls = [call(instruction, chatter, MedicationSearch(comment='theComment', keywords=keywords, brand_names=brands, related_condition=''))]
    assert medications_from.mock_calls == calls
    assert set_medication_dosage.mock_calls == []
    calls = [call()]
    assert current_medications.mock_calls == calls
    calls = [call.get(id='theUuid2')]
    assert medication_db.mock_calls == calls
    calls = [
        call.filter(system='http://www.fdbhealth.com/'),
        call.filter().first(),
    ]
    assert codings_db.mock_calls == calls
    assert chatter.mock_calls == []
    reset_mocks()


@patch.object(LimitedCache, "current_medications")
def test_command_parameters(current_medications):
    def reset_mocks():
        current_medications.reset_mock()

    tested = helper_instance()
    medications = [
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    current_medications.side_effect = [medications]
    result = tested.command_parameters()
    expected = {
        'oldMedication': 'one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)',
        "oldMedicationIndex": "index of the medication to change, or -1, as integer",
        "newMedication": {
            "keywords": "comma separated keywords of up to 5 synonyms of the new medication to prescribe",
            "brandNames": "comma separated of known medication names related to the keywords",
            "sameAsCurrent": "same medication as current one, mandatory, True or False, as boolean"
        },
        "sig": "directions, as free text",
        "suppliedDays": "duration of the treatment in days, as integer",
        "substitution": "one of: allowed/not_allowed",
        "comment": "rationale of the change of prescription including all important words, as free text",
    }
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
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    current_medications.side_effect = [medications]
    result = tested.instruction_description()
    expected = ("Change the prescription of a current medication (display1a, display2a, display3a), "
                "including the new medication, the directions, the duration and the dosage. "
                "There can be only one change of prescription per instruction, and no instruction in the lack of.")
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
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    current_medications.side_effect = [medications]
    result = tested.instruction_constraints()
    expected = ("'AdjustPrescription' has to be related to one of the following medications: "
                "display1a (RxNorm: CODE123), "
                "display2a (RxNorm: CODE45), "
                "display3a (RxNorm: CODE9876)")
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
        CodedItem(uuid="theUuid1", label="display1a", code="CODE123"),
        CodedItem(uuid="theUuid2", label="display2a", code="CODE45"),
        CodedItem(uuid="theUuid3", label="display3a", code="CODE9876"),
    ]
    tests = [
        (medications, True),
        ([], False),
    ]
    for side_effect, expected in tests:
        current_medications.side_effect = [side_effect]
        result = tested.is_available()
        assert result is expected
        calls = [call()]
        assert current_medications.mock_calls == calls
        reset_mocks()
