from __future__ import annotations
from typing import NamedTuple
from evaluations.structures.enums.synthetic_case_turn_buckets import SyntheticCaseTurnBuckets
from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood
from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure
from evaluations.structures.enums.synthetic_case_clinician_style import SyntheticCaseClinicianStyle
from evaluations.structures.enums.synthetic_case_patient_style import SyntheticCasePatientStyle


class Specification(NamedTuple):
    turn_total: int
    speaker_sequence: list[str]
    ratio: float
    mood: list[SyntheticCaseMood]
    pressure: SyntheticCasePressure
    clinician_style: SyntheticCaseClinicianStyle
    patient_style: SyntheticCasePatientStyle
    bucket: SyntheticCaseTurnBuckets

    def to_json(self) -> dict:
        return {
            "turn_total": self.turn_total,
            "speaker_sequence": self.speaker_sequence,
            "ratio": self.ratio,
            "mood": [mood.value for mood in self.mood],
            "pressure": self.pressure.value,
            "clinician_style": self.clinician_style.value,
            "patient_style": self.patient_style.value,
            "bucket": self.bucket.value,
        }

    @classmethod
    def load_from_json(cls, data: dict) -> Specification:
        return cls(
            turn_total=data["turn_total"],
            speaker_sequence=data["speaker_sequence"],
            ratio=data["ratio"],
            mood=[SyntheticCaseMood(mood_str) for mood_str in data["mood"]],
            pressure=SyntheticCasePressure(data["pressure"]),
            clinician_style=SyntheticCaseClinicianStyle(data["clinician_style"]),
            patient_style=SyntheticCasePatientStyle(data["patient_style"]),
            bucket=SyntheticCaseTurnBuckets(data["bucket"]),
        )
