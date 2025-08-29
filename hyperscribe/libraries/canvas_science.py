from http import HTTPStatus
from typing import Type
from urllib.parse import urlencode

from canvas_sdk.commands.commands.allergy import AllergenType
from canvas_sdk.commands.constants import ServiceProvider
from canvas_sdk.utils.http import science_http, ontologies_http
from logger import log

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.allergy_detail import AllergyDetail
from hyperscribe.structures.icd10_condition import Icd10Condition
from hyperscribe.structures.imaging_report import ImagingReport
from hyperscribe.structures.immunization_detail import ImmunizationDetail
from hyperscribe.structures.medical_concept import MedicalConcept
from hyperscribe.structures.medication_detail import MedicationDetail
from hyperscribe.structures.medication_detail_quantity import MedicationDetailQuantity


# note that the "# type: ignore" could be removed if "from typing import TypeVar" was allowed
class CanvasScience:
    @classmethod
    def instructions(cls, expressions: list[str]) -> list[MedicalConcept]:
        return cls.medical_concept("/search/instruction", expressions, MedicalConcept)  # type: ignore

    @classmethod
    def family_histories(cls, expressions: list[str]) -> list[MedicalConcept]:
        return cls.medical_concept("/search/family-history", expressions, MedicalConcept)  # type: ignore

    @classmethod
    def surgical_histories(cls, expressions: list[str]) -> list[MedicalConcept]:
        return cls.medical_concept("/search/surgical-history-procedure", expressions, MedicalConcept)  # type: ignore

    @classmethod
    def medical_histories(cls, expressions: list[str]) -> list[Icd10Condition]:
        return cls.medical_concept("/search/medical-history-condition", expressions, Icd10Condition)  # type: ignore

    @classmethod
    def medication_details(cls, expressions: list[str]) -> list[MedicationDetail]:
        return cls.medical_concept("/search/grouped-medication", expressions, MedicationDetail)  # type: ignore

    @classmethod
    def search_conditions(cls, expressions: list[str]) -> list[Icd10Condition]:
        return cls.medical_concept("/search/condition", expressions, Icd10Condition)  # type: ignore

    @classmethod
    def search_imagings(cls, expressions: list[str]) -> list[ImagingReport]:
        return cls.medical_concept("/parse-templates/imaging-reports", expressions, ImagingReport)  # type: ignore

    @classmethod
    def medical_concept(
        cls,
        url: str,
        expressions: list[str],
        returned_class: Type[MedicalConcept | Icd10Condition | MedicationDetail | ImagingReport],
    ) -> list[MedicalConcept | Icd10Condition | MedicationDetail | ImagingReport]:
        result: list[MedicalConcept | Icd10Condition | MedicationDetail | ImagingReport] = []

        # from canvas_sdk.utils.http import ThreadPoolExecutor
        # with ThreadPoolExecutor(max_workers=10) as get_runner:
        #     all_concepts_thread = list(get_runner.map(lambda expression: cls.get_attempts(
        #         url,
        #         headers=headers,
        #         params={
        #             "query": expression,
        #             "format": "json",
        #             "limit": 10,
        #         }), expressions))

        params = {"format": "json", "limit": 10}
        all_concepts: list = [
            cls.get_attempts(url, params | {"query": expression}, False) for expression in expressions
        ]
        for concepts in all_concepts:
            for concept in concepts:
                if returned_class == MedicationDetail:
                    quantities: list[MedicationDetailQuantity] = []
                    for quantity in concept["clinical_quantities"]:
                        quantities.append(
                            MedicationDetailQuantity(
                                quantity=quantity["erx_quantity"],
                                representative_ndc=quantity["representative_ndc"],
                                ncpdp_quantity_qualifier_code=quantity["erx_ncpdp_script_quantity_qualifier_code"],
                                ncpdp_quantity_qualifier_description=quantity[
                                    "erx_ncpdp_script_quantity_qualifier_description"
                                ],
                            ),
                        )
                    result.append(
                        MedicationDetail(
                            fdb_code=str(concept["med_medication_id"]),
                            description=concept["description_and_quantity"],
                            quantities=quantities,
                        ),
                    )
                elif returned_class == Icd10Condition:
                    result.append(Icd10Condition(code=concept["icd10_code"], label=concept["icd10_text"]))
                elif returned_class == ImagingReport:
                    result.append(ImagingReport(code=concept["code"], name=concept["name"]))
                else:
                    result.append(MedicalConcept(concept_id=concept["concept_id"], term=concept["term"]))
        return result

    @classmethod
    def search_allergy(
        cls,
        expressions: list[str],
        concept_types: list[AllergenType],
    ) -> list[AllergyDetail]:
        result: list = []
        url = "/fdb/allergy/"
        type_values = [t.value for t in concept_types]
        for expression in expressions:
            params = {"dam_allergen_concept_id_description__fts": expression}
            concepts = cls.get_attempts(url, params, True)
            for concept in concepts:
                if concept["dam_allergen_concept_id_type"] in type_values:
                    result.append(
                        AllergyDetail(
                            concept_id_value=int(concept["dam_allergen_concept_id"]),
                            concept_id_description=concept["dam_allergen_concept_id_description"],
                            concept_type=concept["concept_type"],
                            concept_id_type=concept["dam_allergen_concept_id_type"],
                        ),
                    )
        return result

    @classmethod
    def search_immunization(cls, expressions: list[str]) -> list[ImmunizationDetail]:
        result: list = []
        url = "/cpt/immunization/"
        for expression in expressions:
            params = {"name_or_code": expression}
            concepts = cls.get_attempts(url, params, True)
            for concept in concepts:
                result.append(
                    ImmunizationDetail(
                        label=concept["long_name"],
                        code_cpt=concept["cpt_code"],
                        code_cvx=concept["cvx_code"],
                        cvx_description=concept["cvx_description"],
                    ),
                )
        return result

    @classmethod
    def search_contacts(cls, free_text_information: str, zip_codes: list[str]) -> list[ServiceProvider]:
        result: list = []
        url = "/contacts/"

        while free_text_information.strip() and not result:
            params = {"search": free_text_information, "format": "json", "limit": 10}
            if zip_codes:
                params["business_postal_code__in"] = ",".join(zip_codes)

            for contact in cls.get_attempts(url, params, False):
                result.append(
                    ServiceProvider(
                        first_name=contact["firstName"] or "",
                        last_name=contact["lastName"] or "",
                        specialty=contact["specialty"] or "",
                        practice_name=contact["practiceName"] or "",
                        business_address=contact["businessAddress"] or "",
                    ),
                )
            free_text_information = " ".join(free_text_information.rsplit(" ", 1)[:-1])

        return result

    @classmethod
    def get_attempts(cls, url: str, params: dict, is_ontologies: bool) -> list:
        headers = {"Content-Type": "application/json"}

        if params:
            url = f"{url}?{urlencode(params)}"

        for _ in range(Constants.MAX_ATTEMPTS_CANVAS_SERVICES):
            try:
                if is_ontologies:
                    ontologies_http._MAX_REQUEST_TIMEOUT_SECONDS = 7
                    response = ontologies_http.get_json(url, headers)
                    source = "ontologies"
                else:
                    science_http._MAX_REQUEST_TIMEOUT_SECONDS = 7
                    response = science_http.get_json(url, headers)
                    source = "science"

                if response.status_code == HTTPStatus.OK.value:
                    return response.json().get("results") or []

                log.info(f"get response code: {response.status_code} - {source}: {url}")
            except Exception as e:
                log.info(f"error raised by Canvas Service: {e}")
        return []
