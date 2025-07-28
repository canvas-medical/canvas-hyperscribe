from evaluations.structures.enums.synthetic_case_mood import SyntheticCaseMood


def test_enum():
    tested = SyntheticCaseMood
    assert len(tested) == 8
    assert tested.PATIENT_FRUSTRATED.value == "patient is frustrated"
    assert tested.PATIENT_TEARFUL.value == "patient is tearful"
    assert tested.PATIENT_EMBARRASSED.value == "patient is embarrassed"
    assert tested.PATIENT_DEFENSIVE.value == "patient is defensive"
    assert tested.CLINICIAN_CONCERNED.value == "clinician is concerned"
    assert tested.CLINICIAN_RUSHED.value == "clinician is rushed"
    assert tested.CLINICIAN_WARM.value == "clinician is warm"
    assert tested.CLINICIAN_BRIEF.value == "clinician is brief"
