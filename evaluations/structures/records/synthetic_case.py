from __future__ import annotations

from typing import NamedTuple

from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets


class SyntheticCase(NamedTuple):
    case_id: int
    category: str = ""
    turn_total: int = 0
    speaker_sequence: list[str] = []
    clinician_to_patient_turn_ratio: float = 0.0
    mood: list[SyntheticCaseMood] = [SyntheticCaseMood.PATIENT_FRUSTRATED]
    pressure: SyntheticCasePressure = SyntheticCasePressure.TIME_PRESSURE
    clinician_style: SyntheticCaseClinicianStyle = SyntheticCaseClinicianStyle.WARM_CHATTY
    patient_style: SyntheticCasePatientStyle = SyntheticCasePatientStyle.ANXIOUS_TALKATIVE
    turn_buckets: SyntheticCaseTurnBuckets = SyntheticCaseTurnBuckets.SHORT
    duration: float = 0.0
    text_llm_vendor: str = ""
    text_llm_name: str = ""
    temperature: float = 0.0
    id: int = 0

    def duplicate_with(self, case_id: int) -> SyntheticCase:
        """Create a new SyntheticCase instance with the specified case_id, keeping all other fields the same."""
        return SyntheticCase(
            case_id=case_id,
            category=self.category,
            turn_total=self.turn_total,
            speaker_sequence=self.speaker_sequence,
            clinician_to_patient_turn_ratio=self.clinician_to_patient_turn_ratio,
            mood=self.mood,
            pressure=self.pressure,
            clinician_style=self.clinician_style,
            patient_style=self.patient_style,
            turn_buckets=self.turn_buckets,
            duration=self.duration,
            text_llm_vendor=self.text_llm_vendor,
            text_llm_name=self.text_llm_name,
            temperature=self.temperature,
            id=self.id,
        )

    def to_json(self) -> dict:
        return {
            "case_id": self.case_id,
            "category": self.category,
            "turnTotal": self.turn_total,
            "speakerSequence": self.speaker_sequence,
            "clinicianToPatientTurnRatio": self.clinician_to_patient_turn_ratio,
            "mood": [mood.value for mood in self.mood],
            "pressure": self.pressure.value,
            "clinicianStyle": self.clinician_style.value,
            "patientStyle": self.patient_style.value,
            "turnBuckets": self.turn_buckets.value,
            "duration": self.duration,
            "textLlmVendor": self.text_llm_vendor,
            "textLlmName": self.text_llm_name,
            "temperature": self.temperature,
            "id": self.id,
        }
