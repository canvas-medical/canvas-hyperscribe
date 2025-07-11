from enum import Enum


class SyntheticCasePressure(Enum):
    TIME_PRESSURE = "time_pressure"
    DENIED_AUTH = "denied_auth"
    FORMULARY = "formulary"
    REFILL_LIMIT = "refill_limit"
    TRAVELING = "traveling"
    SIDE_EFFECT = "side_effect"