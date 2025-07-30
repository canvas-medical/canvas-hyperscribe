from __future__ import annotations
from typing import NamedTuple


class Chart(NamedTuple):
    demographicStr: str
    conditionHistory: str
    currentAllergies: str
    currentConditions: str
    currentMedications: str
    currentGoals: str
    familyHistory: str
    surgeryHistory: str

    def to_json(self) -> dict:
        return {
            "demographicStr": self.demographicStr,
            "conditionHistory": self.conditionHistory,
            "currentAllergies": self.currentAllergies,
            "currentConditions": self.currentConditions,
            "currentMedications": self.currentMedications,
            "currentGoals": self.currentGoals,
            "familyHistory": self.familyHistory,
            "surgeryHistory": self.surgeryHistory,
        }

    @classmethod
    def load_from_json(cls, data: dict) -> Chart:
        return cls(
            demographicStr=data["demographicStr"],
            conditionHistory=data["conditionHistory"],
            currentAllergies=data["currentAllergies"],
            currentConditions=data["currentConditions"],
            currentMedications=data["currentMedications"],
            currentGoals=data["currentGoals"],
            familyHistory=data["familyHistory"],
            surgeryHistory=data["surgeryHistory"],
        )
