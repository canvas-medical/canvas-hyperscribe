from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.commands.refill import RefillCommand
from canvas_sdk.commands.constants import ClinicalQuantity
from canvas_sdk.v1.data import MedicationCoding, Medication

from hyperscribe.commands.base import Base
from hyperscribe.commands.refill import Refill
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> Refill:
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
    )
    cache = LimitedCache("patientUuid", {})
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


def test_staged_command_extract():
    tested = Refill
    tests = [
        ({}, None),
        ({
             "sig": "theSig",
             "refills": 2,
             "prescribe": {
                 "text": "theMedication",
                 "value": 292907,
             },
             "days_supply": 90,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": "allowed",
             "note_to_pharmacist": "noteToPharmacist",
             "quantity_to_dispense": "30",
         }, CodedItem(
            label="theMedication: theSig (dispense: 30, supply days: 90, refills: 2, substitution: allowed, related conditions: theIndication1/theIndication2/theIndication3)",
            code="",
            uuid="",
        )),
        ({
             "sig": "theSig",
             "refills": 2,
             "prescribe": {
                 "text": "",
                 "value": 292907,
             },
             "days_supply": 90,
             "indications": [
                 {"text": "theIndication1"},
                 {"text": "theIndication2"},
                 {"text": "theIndication3"},
             ],
             "substitutions": "allowed",
             "note_to_pharmacist": "noteToPharmacist",
             "quantity_to_dispense": "30",
         }, None),
        ({
             "sig": "",
             "refills": None,
             "prescribe": {
                 "text": "theMedication",
                 "value": 292907,
             },
             "days_supply": None,
             "indications": [],
             "substitutions": None,
             "note_to_pharmacist": "noteToPharmacist",
             "quantity_to_dispense": None,
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


@patch('hyperscribe.commands.refill.Medication.codings')
@patch('hyperscribe.commands.refill.Medication.objects')
@patch.object(LimitedCache, "current_medications")
def test_command_from_json(current_medications, medication, codings):
    chatter = MagicMock()

    def reset_mocks():
        current_medications.reset_mock()
        medication.reset_mock()
        codings.reset_mock()
        chatter.reset_mock()

    tested = helper_instance()
    medications = [
        CodedItem(uuid="theUuid1", label="display1a", code="123"),
        CodedItem(uuid="theUuid2", label="display2a", code="45"),
        CodedItem(uuid="theUuid3", label="display3a", code="9876"),

    ]
    tests = [
        (1, "theUuid2"),
        (2, "theUuid3"),
    ]
    for idx, medication_uuid in tests:
        current_medications.side_effect = [medications, medications]
        medication.get.side_effect = [Medication(national_drug_code="theNdc", potency_unit_code="thePuc")]
        codings.filter.return_value.first.side_effect = [MedicationCoding(system="theSystem", display="theDisplay", code="theCode"), ]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {
                'comment': 'theComment',
                'medication': 'display2a',
                'medicationIndex': idx,
                'sig': 'theSig',
                'substitution': 'not_allowed',
                'suppliedDays': 7,
            },
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = RefillCommand(
            fdb_code="theCode",
            sig="theSig",
            days_supply=7,
            type_to_dispense=ClinicalQuantity(
                representative_ndc="theNdc",
                ncpdp_quantity_qualifier_code="thePuc",
            ),
            substitutions=PrescribeCommand.Substitutions.NOT_ALLOWED,
            prescriber_id="providerUuid",
            note_uuid="noteUuid",
        )
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        calls = [call()]
        assert current_medications.mock_calls == calls
        calls = [call.get(id=medication_uuid)]
        assert medication.mock_calls == calls
        calls = [
            call.filter(system='http://www.fdbhealth.com/'),
            call.filter().first(),
        ]
        assert codings.mock_calls == calls
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
            'comment': 'theComment',
            'medication': 'display2a',
            'medicationIndex': 4,
            'sig': 'theSig',
            'substitution': 'allowed',
            'suppliedDays': 7,
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
    calls = [call()]
    assert current_medications.mock_calls == calls
    assert medication.mock_calls == []
    assert codings.mock_calls == []
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
        'comment': 'rationale of the prescription, as free text',
        'medication': 'one of: display1a (index: 0)/display2a (index: 1)/display3a (index: 2)',
        'medicationIndex': 'index of the medication to refill, as integer',
        'sig': 'directions, as free text',
        'substitution': 'one of: allowed/not_allowed',
        'suppliedDays': 'duration of the treatment in days, as integer',
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
    expected = ("Refill of a current medication (display1a, display2a, display3a), "
                "including the directions, the duration, the targeted condition and the dosage. "
                "There can be only one refill per instruction, and no instruction in the lack of.")
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
    expected = ("'Refill' has to be related to one of the following medications: "
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
