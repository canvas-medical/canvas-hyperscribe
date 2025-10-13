from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.stop_medication import StopMedicationCommand

from hyperscribe.commands.base import Base
from hyperscribe.commands.stop_medication import StopMedication
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.medication_cached import MedicationCached
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> StopMedication:
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
    cache = LimitedCache()
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return StopMedication(settings, cache, identification)


def test_class():
    tested = StopMedication
    assert issubclass(tested, Base)


def test_schema_key():
    tested = StopMedication
    result = tested.schema_key()
    expected = "stopMedication"
    assert result == expected


def test_staged_command_extract():
    tested = StopMedication
    tests = [
        ({}, None),
        (
            {"medication": {"text": "theMedication"}, "rationale": "theRationale"},
            CodedItem(label="theMedication: theRationale", code="", uuid=""),
        ),
        ({"medication": {"text": ""}, "rationale": "theRationale"}, None),
        (
            {"medication": {"text": "theMedication"}, "rationale": ""},
            CodedItem(label="theMedication: n/a", code="", uuid=""),
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert result == expected


@patch.object(LimitedCache, "current_medications")
@patch.object(StopMedication, "add_code2description")
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
        (1, "theUuid2", [call("theUuid2", "display2")]),
        (2, "theUuid3", [call("theUuid3", "display3")]),
        (4, None, []),
    ]
    for idx, exp_uuid, exp_calls in tests:
        current_medications.side_effect = [medications, medications]
        arguments = {
            "uuid": "theUuid",
            "index": 7,
            "instruction": "theInstruction",
            "information": "theInformation",
            "is_new": False,
            "is_updated": True,
            "parameters": {"medications": "display2a", "medicationIndex": idx, "rationale": "theRationale"},
        }
        instruction = InstructionWithParameters(**arguments)
        result = tested.command_from_json(instruction, chatter)
        command = StopMedicationCommand(rationale="theRationale", note_uuid="noteUuid")
        if exp_uuid is not None:
            command.medication_id = exp_uuid
        expected = InstructionWithCommand(**(arguments | {"command": command}))
        assert result == expected
        assert add_code2description.mock_calls == exp_calls
        calls = [call()]
        assert current_medications.mock_calls == calls
        assert chatter.mock_calls == []
        reset_mocks()


@patch.object(LimitedCache, "current_medications")
def test_command_parameters(current_medications):
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
    current_medications.side_effect = [medications]
    result = tested.command_parameters()
    expected = {
        "medication": "one of: display1 (index: 0)/display2 (index: 1)/display3 (index: 2)",
        "medicationIndex": "index of the medication to stop, or -1, as integer",
        "rationale": "explanation of why the medication is stopped, as free text",
    }
    assert result == expected
    calls = [call()]
    assert current_medications.mock_calls == calls
    reset_mocks()


def test_instruction_description():
    tested = helper_instance()
    result = tested.instruction_description()
    expected = (
        "Stop a medication. "
        "There can be only one medication, with the rationale, to stop per instruction, "
        "and no instruction in the lack of."
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
    current_medications.side_effect = [medications]
    result = tested.instruction_constraints()
    expected = "'StopMedication' has to be related to one of the following medications: display1, display2, display3."
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
            potency_unit_code="puc3",
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
