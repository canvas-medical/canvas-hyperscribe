from evaluations.structures.enums.synthetic_case_pressure import SyntheticCasePressure


def test_enum():
    tested = SyntheticCasePressure
    assert len(tested) == 6
    assert tested.TIME_PRESSURE.value == "time pressure on the visit"
    assert tested.INSURANCE_DENIED.value == "insurance denied prior authorization"
    assert tested.FORMULARY_CHANGE.value == "formulary change"
    assert tested.REFILL_LIMIT.value == "refill limit reached"
    assert tested.PATIENT_TRAVELS.value == "patient traveling soon"
    assert tested.SIDE_EFFECT_REPORT.value == "side-effect report just came in"
