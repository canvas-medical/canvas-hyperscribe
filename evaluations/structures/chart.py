from __future__ import annotations
from typing import NamedTuple


class Chart(NamedTuple):
    demographic_str: str
    condition_history: str
    current_allergies: str
    current_conditions: str
    current_medications: str
    current_goals: str
    family_history: str
    surgery_history: str

    def to_json(self) -> dict:
        return {
            "demographicStr": self.demographic_str,
            "conditionHistory": self.condition_history,
            "currentAllergies": self.current_allergies,
            "currentConditions": self.current_conditions,
            "currentMedications": self.current_medications,
            "currentGoals": self.current_goals,
            "familyHistory": self.family_history,
            "surgeryHistory": self.surgery_history,
        }

    @classmethod
    def load_from_json(cls, data: dict) -> Chart:
        return cls(
            demographic_str=data["demographicStr"],
            condition_history=data["conditionHistory"],
            current_allergies=data["currentAllergies"],
            current_conditions=data["currentConditions"],
            current_medications=data["currentMedications"],
            current_goals=data["currentGoals"],
            family_history=data["familyHistory"],
            surgery_history=data["surgeryHistory"],
        )
