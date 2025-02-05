from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.allergy import AllergenType

from commander.protocols.canvas_science import CanvasScience
from commander.protocols.structures.allergy_detail import AllergyDetail
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


@patch.object(CanvasScience, 'get_attempts')
def test_search_allergy(get_attempts):
    def reset_mocks():
        get_attempts.reset_mock()

    tested = CanvasScience
    host = "theHost"
    shared_key = "theSharedKey"
    headers = {"Authorization": "theSharedKey"}
    expressions = ["expression1", "expression2", "expression3"]

    concepts = [
        {
            "dam_allergen_concept_id_type": 1,
            "dam_allergen_concept_id": "134",
            "dam_allergen_concept_id_description": "descriptionA",
            "concept_type": "conceptTypeA",
        },
        {
            "dam_allergen_concept_id_type": 1,
            "dam_allergen_concept_id": "167",
            "dam_allergen_concept_id_description": "descriptionB",
            "concept_type": "conceptTypeB",
        },
        {
            "dam_allergen_concept_id_type": 2,
            "dam_allergen_concept_id": "234",
            "dam_allergen_concept_id_description": "descriptionC",
            "concept_type": "conceptTypeC",
        },
        {
            "dam_allergen_concept_id_type": 6,
            "dam_allergen_concept_id": "334",
            "dam_allergen_concept_id_description": "descriptionD",
            "concept_type": "conceptTypeD",
        },
        {
            "dam_allergen_concept_id_type": 2,
            "dam_allergen_concept_id": "267",
            "dam_allergen_concept_id_description": "descriptionE",
            "concept_type": "conceptTypeE",
        },
    ]
    details = [
        AllergyDetail(concept_id_value=134, concept_id_description="descriptionA", concept_type="conceptTypeA", concept_id_type=1),
        AllergyDetail(concept_id_value=167, concept_id_description="descriptionB", concept_type="conceptTypeB", concept_id_type=1),
        AllergyDetail(concept_id_value=234, concept_id_description="descriptionC", concept_type="conceptTypeC", concept_id_type=2),
        AllergyDetail(concept_id_value=334, concept_id_description="descriptionD", concept_type="conceptTypeD", concept_id_type=6),
        AllergyDetail(concept_id_value=267, concept_id_description="descriptionE", concept_type="conceptTypeE", concept_id_type=2),
    ]

    tests = [
        (
            [AllergenType.ALLERGEN_GROUP],
            [concepts[:4], [], concepts[4:]],
            [details[i] for i in [0, 1]]
        ),
        (
            [AllergenType.ALLERGEN_GROUP, AllergenType.INGREDIENT],
            [concepts[:4], [], concepts[4:]],
            [details[i] for i in [0, 1, 3]]
        ),
        (
            [AllergenType.MEDICATION],
            [concepts[:4], [], concepts[4:]],
            [details[i] for i in [2, 4]]
        ),
    ]
    for concept_types, side_effects, expected in tests:
        get_attempts.side_effect = side_effects
        result = tested.search_allergy(host, shared_key, expressions, concept_types)
        assert result == expected

        calls = [
            call("theHost/fdb/allergy/", headers=headers, params={"dam_allergen_concept_id_description__fts": "expression1"}),
            call("theHost/fdb/allergy/", headers=headers, params={"dam_allergen_concept_id_description__fts": "expression2"}),
            call("theHost/fdb/allergy/", headers=headers, params={"dam_allergen_concept_id_description__fts": "expression3"}),
        ]
        assert get_attempts.mock_calls == calls
        reset_mocks()


@patch('commander.protocols.canvas_science.log')
@patch('commander.protocols.canvas_science.requests_get')
def test_get_attempts(requests_get, log):
    def reset_mocks():
        requests_get.reset_mock()
        log.reset_mock()

    tested = CanvasScience

    headers = {"header": "value"}
    params = {"param": "value"}

    # too many attempts
    mock_1 = MagicMock()
    mock_1.status_code = 401
    mock_1.json.return_value = {"results": ["mock list 1"]}
    mock_2 = MagicMock()
    mock_2.status_code = 402
    mock_2.json.return_value = {"results": ["mock list 2"]}
    mock_3 = MagicMock()
    mock_3.status_code = 403
    mock_3.json.return_value = {"results": ["mock list 3"]}
    mock_4 = MagicMock()
    mock_4.status_code = 404
    mock_4.json.return_value = {"results": ["mock list 4"]}

    requests_get.side_effect = [mock_1, mock_2, mock_3, mock_4]
    result = tested.get_attempts("theUrl", headers, params)
    assert result == []
    calls = [
        call("theUrl", headers=headers, params=params, verify=True),
        call("theUrl", headers=headers, params=params, verify=True),
        call("theUrl", headers=headers, params=params, verify=True),
    ]
    assert requests_get.mock_calls == calls
    calls = [
        call.info("get response code: 401 - theUrl"),
        call.info("get response code: 402 - theUrl"),
        call.info("get response code: 403 - theUrl"),
    ]
    assert log.mock_calls == calls
    reset_mocks()

    # enough attempts
    mock_2.status_code = 200
    mock_2.json.return_value = {"results": ["mock list 2"]}

    requests_get.side_effect = [mock_1, mock_2, mock_3, mock_4]
    result = tested.get_attempts("theUrl", headers, params)
    assert result == ["mock list 2"]
    calls = [
        call("theUrl", headers=headers, params=params, verify=True),
        call("theUrl", headers=headers, params=params, verify=True),
    ]
    assert requests_get.mock_calls == calls
    calls = [
        call.info("get response code: 401 - theUrl"),
    ]
    assert log.mock_calls == calls
    reset_mocks()
