from enum import Enum


class SyntheticCaseMood(Enum):
    PATIENT_FRUSTRATED = "patient_frustrated"
    PATIENT_TEARFUL = "patient_tearful"
    PATIENT_EMBARRASSED = "patient_embarrassed"
    PATIENT_DEFENSIVE = "patient_defensive"
    CLINICIAN_CONCERNED = "clinician_concerned"
    CLINICIAN_RUSHED = "clinician_rushed"
    CLINICIAN_WARM = "clinician_warm"
    CLINICIAN_BRIEF = "clinician_brief"