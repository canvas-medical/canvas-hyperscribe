from http import HTTPStatus
from typing import Type

from requests import get as requests_get

from commander.protocols.structures.icd10_condition import Icd10Condition
from commander.protocols.structures.medical_concept import MedicalConcept


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
    def medical_concept(cls, url: str, expressions: list[str], returned_class: Type[MedicalConcept | Icd10Condition]) -> list[
        MedicalConcept | Icd10Condition]:
        result: list[MedicalConcept | Icd10Condition] = []
        headers = {
            "Content-Type": "application/json",
        }
        for expression in expressions:
            params = {
                "query": expression,
                "format": "json",
                "limit": 10,
            }
            request = requests_get(
                url,
                headers=headers,
                params=params,
                verify=True,
            )
            if request.status_code == HTTPStatus.OK.value and (concepts := request.json().get("results", [])):
                for concept in concepts:
                    if returned_class == Icd10Condition:
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
