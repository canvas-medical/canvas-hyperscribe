from unittest.mock import patch, call

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.structures.icd10_condition import Icd10Condition
from commander.protocols.structures.medical_concept import MedicalConcept
from commander.protocols.structures.medication_detail import MedicationDetail


@patch.object(CanvasScience, 'medical_concept')
def test_instructions(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.instructions("theHost", ["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call(
        "theHost/search/instruction",
        ["expression 1", "expression 2"],
        MedicalConcept,
    )]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, 'medical_concept')
def test_family_histories(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.family_histories("theHost", ["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call(
        "theHost/search/family-history",
        ["expression 1", "expression 2"],
        MedicalConcept,
    )]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, 'medical_concept')
def test_surgical_histories(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.surgical_histories("theHost", ["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call(
        "theHost/search/surgical-history-procedure",
        ["expression 1", "expression 2"],
        MedicalConcept,
    )]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, 'medical_concept')
def test_medical_histories(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.medical_histories("theHost", ["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call(
        "theHost/search/medical-history-condition",
        ["expression 1", "expression 2"],
        Icd10Condition,
    )]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, 'medical_concept')
def test_medication_details(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.medication_details("theHost", ["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call(
        "theHost/search/grouped-medication",
        ["expression 1", "expression 2"],
        MedicationDetail,
    )]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, 'medical_concept')
def test_search_conditions(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.search_conditions("theHost", ["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call(
        "theHost/search/condition",
        ["expression 1", "expression 2"],
        Icd10Condition,
    )]
    assert medical_concept.mock_calls == calls
    reset_mocks()
