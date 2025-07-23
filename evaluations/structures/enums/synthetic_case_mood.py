from enum import Enum


class SyntheticCaseMood(Enum):
    PATIENT_FRUSTRATED = "patient is frustrated"
    PATIENT_TEARFUL = "patient is tearful"
    PATIENT_EMBARRASSED = "patient is embarrassed"
    PATIENT_DEFENSIVE = "patient is defensive"
    CLINICIAN_CONCERNED = "clinician is concerned"
    CLINICIAN_RUSHED = "clinician is rushed"
    CLINICIAN_WARM = "clinician is warm"
    CLINICIAN_BRIEF = "clinician is brief"
