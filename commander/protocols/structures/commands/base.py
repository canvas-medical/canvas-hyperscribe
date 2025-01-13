from datetime import datetime
from re import match

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.v1.data import Condition
from canvas_sdk.v1.data import Medication
from canvas_sdk.v1.data.condition import ClinicalStatus

from commander.protocols.constants import Constants
from commander.protocols.structures.settings import Settings


class Base:

    def __init__(self, settings: Settings, patient_id: str, note_uuid: str):
        self.settings = settings
        self.patient_id = patient_id
        self.note_uuid = note_uuid
        self._conditions: list | None = None
        self._goals: list | None = None
        self._medications: list | None = None

    def class_name(self) -> str:
        return self.__class__.__name__

    @classmethod
    def str2date(cls, string: str | None) -> datetime | None:
        try:
            return datetime.strptime(string, "%Y-%m-%d")
        except Exception:
            return None

    @classmethod
    def icd10_add_dot(cls, code: str) -> str:
        if result := match(r"([A-Za-z]+\d{2})(\d+)", code):
            return f"{result.group(1)}.{result.group(2)}"
        return code

    def from_json(self, parameters: dict) -> None | _BaseCommand:
        raise NotImplementedError

    def parameters(self) -> dict:
        raise NotImplementedError

    def information(self) -> str:
        raise NotImplementedError

    def is_available(self) -> bool:
        raise NotImplementedError

    def current_goals(self) -> list[dict]:
        if self._goals is None:
            self._goals = []
        return self._goals

    def current_conditions(self) -> list[dict]:
        if not Constants.HAS_DATABASE_ACCESS:
            return [
                {
                    "uuid": "967ab04e-3c4d-45d8-849e-56680f609f0b",
                    "label": "Type 2 diabetes mellitus without complications",
                    "code": "E119",
                },
                {
                    "uuid": "967ab04e-3c4d-45d8-849e-56680f609f00",
                    "label": "Essential (primary) hypertension",
                    "code": "I10",
                },
                {
                    "uuid": "967ab04e-3c4d-45d8-849e-56680f609f01",
                    "label": "Hyperlipidemia, unspecified",
                    "code": "E785",
                },
            ]
        if self._conditions is None:
            self._conditions = []
            for condition in Condition.objects.committed().for_patient(self.patient_id).filter(clinical_status=ClinicalStatus.ACTIVE):
                for coding in condition.codings.all():
                    if coding.system == "ICD-10":
                        self._conditions.append({
                            "uuid": str(condition.id),
                            "label": coding.display,
                            "code": self.icd10_add_dot(coding.code),
                        })
        return self._conditions

    def current_medications(self) -> list[dict]:
        if not Constants.HAS_DATABASE_ACCESS:
            return [
                {
                    "uuid": "967ab04e-3c4d-45d8-849e-56680f609f0b",
                    "label": "lisinopril 20 mg tablet",
                    "code": "314077",
                },
                {
                    "uuid": "967ab04e-3c4d-45d8-849e-56680f609f00",
                    "label": "hydrochlorothiazide 25 mg tablet",
                    "code": "310798",
                },
                {
                    "uuid": "967ab04e-3c4d-45d8-849e-56680f609f01",
                    "label": "Lipitor 10 mg tablet",
                    "code": "617312",
                },
            ]
        if self._medications is None:
            self._medications = []
            for medication in Medication.objects.committed().for_patient(self.patient_id).filter(status=ClinicalStatus.ACTIVE):
                for coding in medication.codings.all():
                    if coding.system == "http://www.nlm.nih.gov/research/umls/rxnorm":
                        self._medications.append({
                            "uuid": str(medication.id),
                            "label": coding.display,
                            "code": coding.code,
                        })
        return self._medications
