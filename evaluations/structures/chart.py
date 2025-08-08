from __future__ import annotations
from typing import NamedTuple
from evaluations.structures.chart_item import ChartItem


class Chart(NamedTuple):
    demographic_str: str
    condition_history: list[ChartItem]
    current_allergies: list[ChartItem]
    current_conditions: list[ChartItem]
    current_medications: list[ChartItem]
    current_goals: list[ChartItem]
    family_history: list[ChartItem]
    surgery_history: list[ChartItem]

    def to_json(self) -> dict:
        return {
            "demographicStr": self.demographic_str,
            "conditionHistory": [item.to_json() for item in self.condition_history],
            "currentAllergies": [item.to_json() for item in self.current_allergies],
            "currentConditions": [item.to_json() for item in self.current_conditions],
            "currentMedications": [item.to_json() for item in self.current_medications],
            "currentGoals": [item.to_json() for item in self.current_goals],
            "familyHistory": [item.to_json() for item in self.family_history],
            "surgeryHistory": [item.to_json() for item in self.surgery_history],
        }

    @classmethod
    def load_from_json(cls, data: dict) -> Chart:
        return cls(
            demographic_str=data["demographicStr"],
            condition_history=[ChartItem.load_from_json(item) for item in data.get("conditionHistory", [])],
            current_allergies=[ChartItem.load_from_json(item) for item in data.get("currentAllergies", [])],
            current_conditions=[ChartItem.load_from_json(item) for item in data.get("currentConditions", [])],
            current_medications=[ChartItem.load_from_json(item) for item in data.get("currentMedications", [])],
            current_goals=[ChartItem.load_from_json(item) for item in data.get("currentGoals", [])],
            family_history=[ChartItem.load_from_json(item) for item in data.get("familyHistory", [])],
            surgery_history=[ChartItem.load_from_json(item) for item in data.get("surgeryHistory", [])],
        )
