from enum import Enum


class SyntheticCasePressure(Enum):
    TIME_PRESSURE = "time pressure on the visit"
    INSURANCE_DENIED = "insurance denied prior authorization"
    FORMULARY_CHANGE = "formulary change"
    REFILL_LIMIT = "refill limit reached"
    PATIENT_TRAVELS = "patient traveling soon"
    SIDE_EFFECT_REPORT = "side-effect report just came in"
