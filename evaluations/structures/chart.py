from __future__ import annotations
from typing import NamedTuple
from hyperscribe.structures.coded_item import CodedItem


class Chart(NamedTuple):
    demographic_str: str
    condition_history: list[CodedItem]
    current_allergies: list[CodedItem]
    current_conditions: list[CodedItem]
    current_medications: list[CodedItem]
    current_goals: list[CodedItem]
    family_history: list[CodedItem]
    surgery_history: list[CodedItem]

    def to_json(self) -> dict:
        return {
            "demographicStr": self.demographic_str,
            "conditionHistory": [item.to_dict() for item in self.condition_history],
            "currentAllergies": [item.to_dict() for item in self.current_allergies],
            "currentConditions": [item.to_dict() for item in self.current_conditions],
            "currentMedications": [item.to_dict() for item in self.current_medications],
            "currentGoals": [item.to_dict() for item in self.current_goals],
            "familyHistory": [item.to_dict() for item in self.family_history],
            "surgeryHistory": [item.to_dict() for item in self.surgery_history],
        }

    @classmethod
    def load_from_json(cls, data: dict) -> Chart:
        return cls(
            demographic_str=data["demographicStr"],
            condition_history=[CodedItem.load_from_json(item) for item in data.get("conditionHistory", [])],
            current_allergies=[CodedItem.load_from_json(item) for item in data.get("currentAllergies", [])],
            current_conditions=[CodedItem.load_from_json(item) for item in data.get("currentConditions", [])],
            current_medications=[CodedItem.load_from_json(item) for item in data.get("currentMedications", [])],
            current_goals=[CodedItem.load_from_json(item) for item in data.get("currentGoals", [])],
            family_history=[CodedItem.load_from_json(item) for item in data.get("familyHistory", [])],
            surgery_history=[CodedItem.load_from_json(item) for item in data.get("surgeryHistory", [])],
        )
