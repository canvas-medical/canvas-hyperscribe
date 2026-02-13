from unittest.mock import patch, call, MagicMock

from canvas_sdk.commands.commands.allergy import AllergenType
from canvas_sdk.commands.constants import ServiceProvider

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.structures.allergy_detail import AllergyDetail
from hyperscribe.structures.icd10_condition import Icd10Condition
from hyperscribe.structures.imaging_report import ImagingReport
from hyperscribe.structures.immunization_detail import ImmunizationDetail
from hyperscribe.structures.medical_concept import MedicalConcept
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_detail_quantity import MedicationDetailQuantity


@patch.object(CanvasScience, "medical_concept")
def test_instructions(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.instructions(["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call("/search/instruction", ["expression 1", "expression 2"], MedicalConcept)]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, "medical_concept")
def test_family_histories(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.family_histories(["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call("/search/family-history", ["expression 1", "expression 2"], MedicalConcept)]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, "medical_concept")
def test_surgical_histories(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.surgical_histories(["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call("/search/surgical-history-procedure", ["expression 1", "expression 2"], MedicalConcept)]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, "medical_concept")
def test_medical_histories(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.medical_histories(["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call("/search/medical-history-condition", ["expression 1", "expression 2"], Icd10Condition)]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, "medical_concept")
def test_medication_details(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.medication_details(["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call("/search/grouped-medication", ["expression 1", "expression 2"], MedicationDetail)]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, "medical_concept")
def test_search_conditions(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.search_conditions(["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call("/search/condition", ["expression 1", "expression 2"], Icd10Condition)]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, "medical_concept")
def test_search_imagings(medical_concept):
    def reset_mocks():
        medical_concept.reset_mock()

    tested = CanvasScience

    medical_concept.side_effect = ["medical_concept was called"]
    result = tested.search_imagings(["expression 1", "expression 2"])
    expected = "medical_concept was called"
    assert result == expected
    calls = [call("/parse-templates/imaging-reports", ["expression 1", "expression 2"], ImagingReport)]
    assert medical_concept.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, "get_attempts")
def test_medical_concept(get_attempts):
    def reset_mocks():
        get_attempts.reset_mock()

    tested = CanvasScience
    url = "theUrl"
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
            ],
        ),
        (
            Icd10Condition,
            [
                [{"icd10_code": "code123", "icd10_text": "labelA"}, {"icd10_code": "code369", "icd10_text": "labelB"}],
                [{"icd10_code": "code752", "icd10_text": "labelC"}],
                [],
            ],
            [
                Icd10Condition(code="code123", label="labelA"),
                Icd10Condition(code="code369", label="labelB"),
                Icd10Condition(code="code752", label="labelC"),
            ],
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
                    {"med_medication_id": 369, "description_and_quantity": "labelB", "clinical_quantities": []},
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
                MedicationDetail(fdb_code="369", description="labelB", quantities=[]),
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
            ],
        ),
        (
            ImagingReport,
            [
                [
                    {
                        "id": 5471,
                        "fields": [
                            {
                                "id": 16562,
                                "type": "text",
                                "code_system": "CPT",
                                "options": [],
                                "sequence": 1,
                                "code": "codeFieldA1",
                                "label": "Comment",
                                "units": None,
                                "required": False,
                            },
                        ],
                        "name": "NameA",
                        "score": 0,
                        "code": "codeA",
                        "code_system": "CPT",
                        "search_keywords": "keywordA1, keywordA2",
                        "active": True,
                        "custom": False,
                        "long_name": "LongNameA",
                        "rank": 10,
                    },
                    {
                        "id": 5587,
                        "fields": [],
                        "name": "NameB",
                        "score": 0,
                        "code": "codeB",
                        "code_system": "CPT",
                        "search_keywords": "keywordB1",
                        "active": True,
                        "custom": True,
                        "long_name": "LongNameB",
                        "rank": 10,
                    },
                ],
                [
                    {
                        "id": 6325,
                        "fields": [],
                        "name": "NameC",
                        "score": 0,
                        "code": "codeC",
                        "code_system": "CPT",
                        "search_keywords": "keywordC1, keywordC2, keywordC3",
                        "active": False,
                        "custom": False,
                        "long_name": "LongNameB",
                        "rank": 10,
                    },
                ],
                [],
            ],
            [
                ImagingReport(code="codeA", name="NameA"),
                ImagingReport(code="codeB", name="NameB"),
                ImagingReport(code="codeC", name="NameC"),
            ],
        ),
    ]
    for returned_class, side_effects, expected in tests:
        get_attempts.side_effect = side_effects
        result = tested.medical_concept(url, expressions, returned_class)
        assert result == expected

        calls = [
            call(url, params | {"query": "expression1"}, False),
            call(url, params | {"query": "expression2"}, False),
            call(url, params | {"query": "expression3"}, False),
        ]
        assert get_attempts.mock_calls == calls
        reset_mocks()

    # empty/whitespace expressions are skipped
    for empty_expressions in [[""], ["", "  ", " "], []]:
        get_attempts.side_effect = []
        result = tested.medical_concept(url, empty_expressions, MedicalConcept)
        assert result == []
        assert get_attempts.mock_calls == []
        reset_mocks()

    # mixed: only non-empty expressions trigger API calls
    get_attempts.side_effect = [
        [{"concept_id": 123, "term": "termA"}],
    ]
    result = tested.medical_concept(url, ["", "expression1", "  "], MedicalConcept)
    assert result == [MedicalConcept(concept_id=123, term="termA")]
    calls = [call(url, params | {"query": "expression1"}, False)]
    assert get_attempts.mock_calls == calls
    reset_mocks()


@patch.object(CanvasScience, "get_attempts")
def test_search_allergy(get_attempts):
    def reset_mocks():
        get_attempts.reset_mock()

    tested = CanvasScience
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
        AllergyDetail(
            concept_id_value=134,
            concept_id_description="descriptionA",
            concept_type="conceptTypeA",
            concept_id_type=1,
        ),
        AllergyDetail(
            concept_id_value=167,
            concept_id_description="descriptionB",
            concept_type="conceptTypeB",
            concept_id_type=1,
        ),
        AllergyDetail(
            concept_id_value=234,
            concept_id_description="descriptionC",
            concept_type="conceptTypeC",
            concept_id_type=2,
        ),
        AllergyDetail(
            concept_id_value=334,
            concept_id_description="descriptionD",
            concept_type="conceptTypeD",
            concept_id_type=6,
        ),
        AllergyDetail(
            concept_id_value=267,
            concept_id_description="descriptionE",
            concept_type="conceptTypeE",
            concept_id_type=2,
        ),
    ]

    tests = [
        ([AllergenType.ALLERGEN_GROUP], [concepts[:4], [], concepts[4:]], [details[i] for i in [0, 1]]),
        (
            [AllergenType.ALLERGEN_GROUP, AllergenType.INGREDIENT],
            [concepts[:4], [], concepts[4:]],
            [details[i] for i in [0, 1, 3]],
        ),
        ([AllergenType.MEDICATION], [concepts[:4], [], concepts[4:]], [details[i] for i in [2, 4]]),
    ]
    for concept_types, side_effects, expected in tests:
        get_attempts.side_effect = side_effects
        result = tested.search_allergy(expressions, concept_types)
        assert result == expected

        calls = [
            call(
                "/fdb/allergy/",
                {"dam_allergen_concept_id_description__fts": "expression1"},
                True,
            ),
            call(
                "/fdb/allergy/",
                {"dam_allergen_concept_id_description__fts": "expression2"},
                True,
            ),
            call(
                "/fdb/allergy/",
                {"dam_allergen_concept_id_description__fts": "expression3"},
                True,
            ),
        ]
        assert get_attempts.mock_calls == calls
        reset_mocks()


@patch.object(CanvasScience, "get_attempts")
def test_search_immunization(get_attempts):
    def reset_mocks():
        get_attempts.reset_mock()

    tested = CanvasScience
    expressions = ["expression1", "expression2", "expression3"]

    concepts = [
        {
            "cpt_code": "cptCode1",
            "cvx_code": "cvxCode1",
            "long_name": "theLongName1",
            "medium_name": "theMediumName1",
            "cvx_description": "theDescription1",
        },
        {
            "cpt_code": "cptCode2",
            "cvx_code": "cvxCode2",
            "long_name": "theLongName2",
            "medium_name": "theMediumName2",
            "cvx_description": "theDescription2",
        },
        {
            "cpt_code": "cptCode3",
            "cvx_code": "cvxCode3",
            "long_name": "theLongName3",
            "medium_name": "theMediumName3",
            "cvx_description": "theDescription3",
        },
    ]
    details = [
        ImmunizationDetail(
            label="theLongName1",
            code_cpt="cptCode1",
            code_cvx="cvxCode1",
            cvx_description="theDescription1",
        ),
        ImmunizationDetail(
            label="theLongName2",
            code_cpt="cptCode2",
            code_cvx="cvxCode2",
            cvx_description="theDescription2",
        ),
        ImmunizationDetail(
            label="theLongName3",
            code_cpt="cptCode3",
            code_cvx="cvxCode3",
            cvx_description="theDescription3",
        ),
    ]

    tests = [
        ([concepts[0:1], concepts[1:3], []], details),
        ([[], [], []], []),
    ]
    for side_effects, expected in tests:
        get_attempts.side_effect = side_effects
        result = tested.search_immunization(expressions)
        assert result == expected

        calls = [
            call("/cpt/immunization/", {"name_or_code": "expression1"}, True),
            call("/cpt/immunization/", {"name_or_code": "expression2"}, True),
            call("/cpt/immunization/", {"name_or_code": "expression3"}, True),
        ]
        assert get_attempts.mock_calls == calls
        reset_mocks()


@patch.object(CanvasScience, "get_attempts")
def test_search_contacts(get_attempts):
    def reset_mocks():
        get_attempts.reset_mock()

    tested = CanvasScience
    side_effect = [
        {
            "firstName": "theFirstName1",
            "lastName": "theLastName1",
            "specialty": "theSpecialty1",
            "practiceName": "thePracticeName1",
            "businessAddress": "theBusinessAddress1",
        },
        {
            "firstName": "theFirstName2",
            "lastName": "theLastName2",
            "specialty": "theSpecialty2",
            "practiceName": "thePracticeName2",
            "businessAddress": "theBusinessAddress2",
        },
        {
            "firstName": "theFirstName3",
            "lastName": "theLastName3",
            "specialty": "theSpecialty3",
            "practiceName": "thePracticeName3",
            "businessAddress": "theBusinessAddress3",
        },
    ]
    expected = [
        ServiceProvider(
            first_name="theFirstName1",
            last_name="theLastName1",
            specialty="theSpecialty1",
            practice_name="thePracticeName1",
            business_address="theBusinessAddress1",
        ),
        ServiceProvider(
            first_name="theFirstName2",
            last_name="theLastName2",
            specialty="theSpecialty2",
            practice_name="thePracticeName2",
            business_address="theBusinessAddress2",
        ),
        ServiceProvider(
            first_name="theFirstName3",
            last_name="theLastName3",
            specialty="theSpecialty3",
            practice_name="thePracticeName3",
            business_address="theBusinessAddress3",
        ),
    ]
    # no zip codes
    get_attempts.side_effect = [[], side_effect]
    result = tested.search_contacts("theFree Text Information", [])
    assert result == expected
    calls = [
        call("/contacts/", {"search": "theFree Text Information", "format": "json", "limit": 10}, False),
        call("/contacts/", {"search": "theFree Text", "format": "json", "limit": 10}, False),
    ]
    assert get_attempts.mock_calls == calls
    reset_mocks()
    # with zip codes
    get_attempts.side_effect = [[], side_effect]
    result = tested.search_contacts("theFree Text Information", ["zip1", "zip2"])
    assert result == expected
    calls = [
        call(
            "/contacts/",
            {
                "search": "theFree Text Information",
                "business_postal_code__in": "zip1,zip2",
                "format": "json",
                "limit": 10,
            },
            False,
        ),
        call(
            "/contacts/",
            {"search": "theFree Text", "business_postal_code__in": "zip1,zip2", "format": "json", "limit": 10},
            False,
        ),
    ]
    assert get_attempts.mock_calls == calls
    reset_mocks()
    # no results
    get_attempts.side_effect = [[], [], []]
    result = tested.search_contacts("theFree Text Information", [])
    assert result == []
    calls = [
        call("/contacts/", {"search": "theFree Text Information", "format": "json", "limit": 10}, False),
        call("/contacts/", {"search": "theFree Text", "format": "json", "limit": 10}, False),
        call("/contacts/", {"search": "theFree", "format": "json", "limit": 10}, False),
    ]
    assert get_attempts.mock_calls == calls
    reset_mocks()


@patch("hyperscribe.libraries.canvas_science.ontologies_http")
@patch("hyperscribe.libraries.canvas_science.science_http")
@patch("hyperscribe.libraries.canvas_science.log")
def test_get_attempts(log, science, ontologies):
    mock_1 = MagicMock()
    mock_2 = MagicMock()
    mock_3 = MagicMock()
    mock_4 = MagicMock()

    def reset_mocks():
        log.reset_mock()
        science.reset_mock()
        ontologies.reset_mock()
        mock_1.reset_mock()
        mock_2.reset_mock()
        mock_3.reset_mock()
        mock_4.reset_mock()

    tested = CanvasScience

    headers_no_key = {"Content-Type": "application/json"}
    params = {"param": "value"}

    # too many attempts
    mock_1.status_code = 401
    mock_1.json.return_value = {"results": ["mock list 1"]}
    mock_2.status_code = 402
    mock_2.json.return_value = {"results": ["mock list 2"]}
    mock_3.status_code = 403
    mock_3.json.return_value = {"results": ["mock list 3"]}
    mock_4.status_code = 404
    mock_4.json.return_value = {"results": ["mock list 4"]}

    science.get_json.side_effect = [mock_1, mock_2, mock_3, mock_4]
    ontologies.get_json.side_effect = []
    result = tested.get_attempts("/theUrl", params, False)
    assert result == []
    calls = [
        call.info("get response code: 401 - science: /theUrl?param=value"),
        call.info("get response code: 402 - science: /theUrl?param=value"),
    ]
    assert log.mock_calls == calls
    calls = [
        call.get_json("/theUrl?param=value", {"Content-Type": "application/json"}),
        call.get_json("/theUrl?param=value", {"Content-Type": "application/json"}),
    ]
    assert science.mock_calls == calls
    assert ontologies.mock_calls == []
    assert mock_1.mock_calls == []
    assert mock_2.mock_calls == []
    assert mock_3.mock_calls == []
    assert mock_4.mock_calls == []
    reset_mocks()

    # enough attempts
    mock_2.status_code = 200
    mock_2.json.return_value = {"results": ["mock list 2"]}

    science.get_json.side_effect = [mock_1, mock_2, mock_3, mock_4]
    ontologies.get_json.side_effect = []
    result = tested.get_attempts("/theUrl", params, False)
    assert result == ["mock list 2"]
    calls = [call.info("get response code: 401 - science: /theUrl?param=value")]
    assert log.mock_calls == calls
    calls = [
        call.get_json("/theUrl?param=value", {"Content-Type": "application/json"}),
        call.get_json("/theUrl?param=value", {"Content-Type": "application/json"}),
    ]
    assert science.mock_calls == calls
    assert ontologies.mock_calls == []
    assert mock_1.mock_calls == []
    assert mock_2.mock_calls == [call.json()]
    assert mock_3.mock_calls == []
    assert mock_4.mock_calls == []
    reset_mocks()

    # using SDK Ontologies
    mock_2.status_code = 200
    mock_2.json.return_value = {"results": ["mock list 2"]}

    science.get_json.side_effect = []
    ontologies.get_json.side_effect = [mock_1, mock_2, mock_3, mock_4]
    result = tested.get_attempts("/theUrl", params, True)
    assert result == ["mock list 2"]
    calls = [call.info("get response code: 401 - ontologies: /theUrl?param=value")]
    assert log.mock_calls == calls
    assert science.mock_calls == []
    calls = [
        call.get_json("/theUrl?param=value", headers_no_key),
        call.get_json("/theUrl?param=value", headers_no_key),
    ]
    assert ontologies.mock_calls == calls
    assert mock_1.mock_calls == []
    assert mock_2.mock_calls == [call.json()]
    assert mock_3.mock_calls == []
    assert mock_4.mock_calls == []
    reset_mocks()

    # using SDK Sciences
    mock_2.status_code = 200
    mock_2.json.return_value = {"results": ["mock list 2"]}

    science.get_json.side_effect = [mock_1, mock_2, mock_3, mock_4]
    ontologies.get_json.side_effect = []
    result = tested.get_attempts("/theUrl", params, False)
    assert result == ["mock list 2"]
    calls = [call.info("get response code: 401 - science: /theUrl?param=value")]
    assert log.mock_calls == calls
    calls = [
        call.get_json("/theUrl?param=value", headers_no_key),
        call.get_json("/theUrl?param=value", headers_no_key),
    ]
    assert science.mock_calls == calls
    assert ontologies.mock_calls == []
    assert mock_1.mock_calls == []
    assert mock_2.mock_calls == [call.json()]
    assert mock_3.mock_calls == []
    assert mock_4.mock_calls == []
    reset_mocks()
    # -- no key, no params
    mock_2.status_code = 200
    mock_2.json.return_value = {"results": ["mock list 2"]}

    science.get_json.side_effect = [mock_1, mock_2, mock_3, mock_4]
    ontologies.get_json.side_effect = []
    result = tested.get_attempts("/theUrl", {}, False)
    assert result == ["mock list 2"]
    calls = [call.info("get response code: 401 - science: /theUrl")]
    assert log.mock_calls == calls
    calls = [
        call.get_json("/theUrl", headers_no_key),
        call.get_json("/theUrl", headers_no_key),
    ]
    assert science.mock_calls == calls
    assert ontologies.mock_calls == []
    assert mock_1.mock_calls == []
    assert mock_2.mock_calls == [call.json()]
    assert mock_3.mock_calls == []
    assert mock_4.mock_calls == []
    reset_mocks()

    # -- exception
    mock_2.status_code = 200
    mock_2.json.side_effect = [Exception("Test error")]

    science.get_json.side_effect = [mock_1, mock_2, mock_3, mock_4]
    ontologies.get_json.side_effect = []
    result = tested.get_attempts("/theUrl", {}, False)
    assert result == []
    calls = [
        call.info("get response code: 401 - science: /theUrl"),
        call.info("error raised by Canvas Service: Test error"),
    ]
    assert log.mock_calls == calls
    calls = [
        call.get_json("/theUrl", headers_no_key),
        call.get_json("/theUrl", headers_no_key),
    ]
    assert science.mock_calls == calls
    assert ontologies.mock_calls == []
    assert mock_1.mock_calls == []
    assert mock_2.mock_calls == [call.json()]
    assert mock_3.mock_calls == []
    assert mock_4.mock_calls == []
    reset_mocks()
