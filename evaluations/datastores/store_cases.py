import json
from pathlib import Path

from evaluations.structures.evaluation_case import EvaluationCase


class StoreCases:
    @classmethod
    def _db_path(cls) -> Path:
        return Path(__file__).parent / "cases"

    @classmethod
    def upsert(cls, case: EvaluationCase) -> None:
        file_path = cls._db_path() / f"{case.case_name}.json"
        with file_path.open(mode="w") as f:
            f.write(json.dumps({
                "environment": case.environment,
                "patientUuid": case.patient_uuid,
                "caseType": case.case_type,
                "caseGroup": case.case_group,
                "caseName": case.case_name,
                "description": case.description,
            }, indent=2))

        cache_path = cls._db_path() / f"limited_caches/{case.case_name}.json"
        with cache_path.open(mode="w") as cache:
            cache.write(json.dumps(case.limited_cache, indent=2))

    @classmethod
    def delete(cls, case_name: str) -> None:
        file_path = cls._db_path() / f"{case_name}.json"
        if file_path.exists():
            file_path.unlink()
        cache_path = cls._db_path() / f"limited_caches/{case_name}.json"
        if cache_path.exists():
            cache_path.unlink()

    @classmethod
    def get(cls, case_name: str) -> EvaluationCase:
        result = EvaluationCase()
        file_path = cls._db_path() / f"{case_name}.json"
        cache_path = cls._db_path() / f"limited_caches/{case_name}.json"
        cache = {}

        if cache_path.exists():
            cache = json.loads(cache_path.read_text())

        if file_path.exists():
            data = json.loads(file_path.read_text())
            result = EvaluationCase(
                environment=data["environment"],
                patient_uuid=data["patientUuid"],
                limited_cache=cache,
                case_type=data["caseType"],
                case_group=data["caseGroup"],
                case_name=data["caseName"],
                description=data["description"],
            )
        return result

    @classmethod
    def all(cls) -> list[EvaluationCase]:
        result: list[EvaluationCase] = []
        for file_path in cls._db_path().glob("*.json"):
            data = json.loads(file_path.read_text())
            result.append(EvaluationCase(
                environment=data["environment"],
                patient_uuid=data["patientUuid"],
                case_type=data["caseType"],
                case_group=data["caseGroup"],
                case_name=data["caseName"],
                description=data["description"],
            ))
        return result
