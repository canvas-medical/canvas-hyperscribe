from http import HTTPStatus
from typing import Type

from canvas_sdk.commands.commands.allergy import AllergenType
from logger import log
from requests import get as requests_get

from commander.protocols.structures.allergy_detail import AllergyDetail
from commander.protocols.structures.icd10_condition import Icd10Condition
from commander.protocols.structures.medical_concept import MedicalConcept
from commander.protocols.structures.medication_detail import MedicationDetail
from commander.protocols.structures.medication_detail_quantity import MedicationDetailQuantity


class CanvasScience:
    @classmethod
    def instructions(cls, host: str, expressions: list[str]) -> list[MedicalConcept]:
        return cls.medical_concept(f"{host}/search/instruction", expressions, MedicalConcept)

    @classmethod
    def family_histories(cls, host: str, expressions: list[str]) -> list[MedicalConcept]:
        return cls.medical_concept(f"{host}/search/family-history", expressions, MedicalConcept)

    @classmethod
    def surgical_histories(cls, host: str, expressions: list[str]) -> list[MedicalConcept]:
        return cls.medical_concept(f"{host}/search/surgical-history-procedure", expressions, MedicalConcept)

    @classmethod
    def medical_histories(cls, host: str, expressions: list[str]) -> list[Icd10Condition]:
        return cls.medical_concept(f"{host}/search/medical-history-condition", expressions, Icd10Condition)

    @classmethod
    def medication_details(cls, host: str, expressions: list[str]) -> list[MedicationDetail]:
        return cls.medical_concept(f"{host}/search/grouped-medication", expressions, MedicationDetail)

    @classmethod
    def search_conditions(cls, host: str, expressions: list[str]) -> list[Icd10Condition]:
        return cls.medical_concept(f"{host}/search/condition", expressions, Icd10Condition)

    @classmethod
    def medical_concept(
            cls,
            url: str,
            expressions: list[str],
            returned_class: Type[MedicalConcept | Icd10Condition | MedicationDetail],
    ) -> list[MedicalConcept | Icd10Condition | MedicationDetail]:
        result: list[MedicalConcept | Icd10Condition | MedicationDetail] = []
        headers = {
            "Content-Type": "application/json",
        }
        for expression in expressions:
            params = {
                "query": expression,
                "format": "json",
                "limit": 10,
            }
            concepts = cls.get_attempts(url, headers=headers, params=params)
            for concept in concepts:
                if returned_class == MedicationDetail:
                    quantities: list[MedicationDetailQuantity] = []
                    for quantity in concept["clinical_quantities"]:
                        quantities.append(MedicationDetailQuantity(
                            quantity=quantity["erx_quantity"],
                            representative_ndc=quantity["representative_ndc"],
                            ncpdp_quantity_qualifier_code=quantity["erx_ncpdp_script_quantity_qualifier_code"],
                            ncpdp_quantity_qualifier_description=quantity["erx_ncpdp_script_quantity_qualifier_description"],
                        ))
                    result.append(MedicationDetail(
                        fdb_code=str(concept["med_medication_id"]),
                        description=concept["description_and_quantity"],
                        quantities=quantities,
                    ))
                elif returned_class == Icd10Condition:
                    result.append(Icd10Condition(
                        code=concept["icd10_code"],
                        label=concept["icd10_text"],
                    ))
                else:
                    result.append(MedicalConcept(
                        concept_id=concept["concept_id"],
                        term=concept["term"],
                    ))
        return result

    @classmethod
    def search_allergy(cls, host: str, pre_shared_key: str, expressions: list[str], concept_types: list[AllergenType]) -> list[AllergyDetail]:
        result: list = []
        url = f"{host}/fdb/allergy/"
        headers = {
            "Authorization": pre_shared_key,
        }
        type_values = [t.value for t in concept_types]
        for expression in expressions:
            params = {"dam_allergen_concept_id_description__fts": expression}
            concepts = cls.get_attempts(url, headers=headers, params=params)
            for concept in concepts:
                if concept["dam_allergen_concept_id_type"] in type_values:
                    result.append(
                        AllergyDetail(
                            concept_id_value=int(concept["dam_allergen_concept_id"]),
                            concept_id_description=concept["dam_allergen_concept_id_description"],
                            concept_type=concept["concept_type"],
                            concept_id_type=concept["dam_allergen_concept_id_type"],
                        )
                    )
        return result

    @classmethod
    def get_attempts(cls, url: str, headers: dict, params: dict) -> list:
        max_attempts = 3
        for _ in range(max_attempts):
            request = requests_get(url, headers=headers, params=params, verify=True)
            if request.status_code == HTTPStatus.OK.value:
                return request.json().get("results", [])
            log.info(f"get response code: {request.status_code} - {url}")
        return []
