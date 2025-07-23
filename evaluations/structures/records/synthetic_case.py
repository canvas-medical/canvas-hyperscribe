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
    speaker_sequence: str = ""
    clinician_to_patient_turn_ratio: float = 0.0
    mood: SyntheticCaseMood = SyntheticCaseMood.PATIENT_FRUSTRATED
    pressure: SyntheticCasePressure = SyntheticCasePressure.TIME_PRESSURE
    clinician_style: SyntheticCaseClinicianStyle = SyntheticCaseClinicianStyle.WARM_CHATTY
    patient_style: SyntheticCasePatientStyle = SyntheticCasePatientStyle.ANXIOUS_TALKATIVE
    turn_buckets: SyntheticCaseTurnBuckets = SyntheticCaseTurnBuckets.SHORT
    duration: float = 0.0
    text_llm_vendor: str = ""
    text_llm_name: str = ""
    id: int = 0
