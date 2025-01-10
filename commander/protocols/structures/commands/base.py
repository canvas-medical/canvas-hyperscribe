from datetime import datetime
from re import match

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.v1.data import Condition
from canvas_sdk.v1.data.condition import ClinicalStatus

from commander.protocols.constants import Constants


class Base:

    def __init__(self, openai_key: str, patient_id: str, note_uuid: str):
        self.openai_key = openai_key
        self.patient_id = patient_id
        self.note_uuid = note_uuid
        self._goals: list | None = None
        self._conditions: list | None = None

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
            return []
        if self._conditions is None:
            for condition in Condition.objects.committed().for_patient(self.patient_id).filter(clinical_status=ClinicalStatus.ACTIVE):
                for coding in condition.codings.all():
                    if coding.system == "ICD-10":
                        self._conditions.append({
                            "uuid": str(condition.id),
                            "label": coding.display,
                            "code": self.icd10_add_dot(coding.code),
                        })
        return self._conditions
