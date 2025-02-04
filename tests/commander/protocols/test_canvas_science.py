from unittest.mock import patch, call

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.structures.icd10_condition import Icd10Condition
from commander.protocols.structures.medical_concept import MedicalConcept
from commander.protocols.structures.medication_detail import MedicationDetail
from commander.protocols.structures.medication_detail_quantity import MedicationDetailQuantity


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


@patch.object(CanvasScience, 'get_attempts')
def test_medical_concept(get_attempts):
    def reset_mocks():
        get_attempts.reset_mock()

    tested = CanvasScience
    url = "theUrl"
    headers = {"Content-Type": "application/json"}
    params = {"format": "json", "limit": 10}
    expressions = ["expression1", "expression2", "expression3"]

    tests = [
        (
            MedicalConcept,
            [
                [{"concept_id": 123, "term": "termA"}, {"concept_id": 369, "term": "termB"}],
                [],
                [{"concept_id": 752, "term": "termC"}],
            ],
            [
                MedicalConcept(concept_id=123, term="termA"),
                MedicalConcept(concept_id=369, term="termB"),
                MedicalConcept(concept_id=752, term="termC"),
            ]
        ),
        (
            Icd10Condition,
            [
                [
                    {"icd10_code": "code123", "icd10_text": "labelA"},
                    {"icd10_code": "code369", "icd10_text": "labelB"},
                ],
                [{"icd10_code": "code752", "icd10_text": "labelC"}],
                [],
            ],
            [
                Icd10Condition(code="code123", label="labelA"),
                Icd10Condition(code="code369", label="labelB"),
                Icd10Condition(code="code752", label="labelC"),
            ]
        ),
        (
            MedicationDetail,
            [
                [
                    {
                        "med_medication_id": 123,
                        "description_and_quantity": "labelA",
                        "clinical_quantities": [
                            {
                                "erx_quantity": "7",
                                "representative_ndc": "ndc1",
                                "erx_ncpdp_script_quantity_qualifier_code": "qualifier1",
                                "erx_ncpdp_script_quantity_qualifier_description": "description1",
                            },
                            {
                                "erx_quantity": "3",
                                "representative_ndc": "ndc2",
                                "erx_ncpdp_script_quantity_qualifier_code": "qualifier2",
                                "erx_ncpdp_script_quantity_qualifier_description": "description2",
                            },
                        ],
                    },
                    {
                        "med_medication_id": 369,
                        "description_and_quantity": "labelB",
                        "clinical_quantities": [],
                    },
                ],
                [
                    {
                        "med_medication_id": 752,
                        "description_and_quantity": "labelC",
                        "clinical_quantities": [
                            {
                                "erx_quantity": "6",
                                "representative_ndc": "ndc3",
                                "erx_ncpdp_script_quantity_qualifier_code": "qualifier3",
                                "erx_ncpdp_script_quantity_qualifier_description": "description3",
                            },
                        ],
                    },
                ],
                [],
            ],
            [
                MedicationDetail(
                    fdb_code="123",
                    description="labelA",
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
                ),
                MedicationDetail(
                    fdb_code="369",
                    description="labelB",
                    quantities=[
                    ],
                ),
                MedicationDetail(
                    fdb_code="752",
                    description="labelC",
                    quantities=[
                        MedicationDetailQuantity(
                            quantity="6",
                            representative_ndc="ndc3",
                            ncpdp_quantity_qualifier_code="qualifier3",
                            ncpdp_quantity_qualifier_description="description3",
                        ),
                    ],
                ),
            ]
        ),
    ]
    for returned_class, side_effects, expected in tests:
        get_attempts.side_effect = side_effects
        result = tested.medical_concept(url, expressions, returned_class)
        assert result == expected

        calls = [
            call(url, headers=headers, params=params | {"query": "expression1"}),
            call(url, headers=headers, params=params | {"query": "expression2"}),
            call(url, headers=headers, params=params | {"query": "expression3"}),
        ]
        assert get_attempts.mock_calls == calls
        reset_mocks()
