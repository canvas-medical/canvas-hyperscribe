"""Tests for problem-list-aware code refinement in Scribe normalization output.

Background (KOALA-5603): Nabla's ``/generate-normalized-data`` endpoint
sometimes emits the unspecified parent code (e.g. ``E11.9`` Type 2 DM without
complications) when the patient already has a more specific active condition
on file (e.g. ``E11.65`` Type 2 DM with hyperglycemia). The frontend's existing
diagnose -> assess "belt" only converts when the diagnose's ICD-10 matches a
patient's active condition *exactly*, so the unspecified-parent code from Nabla
slips through as a stand-alone diagnose. Provider must then manually swap.

The helper under test, ``prefer_patient_specific_codes``, post-processes the
``NormalizedData.conditions`` list by rewriting any Nabla coding whose ICD-10
code is the unspecified-parent of a more specific active condition on the
patient's problem list. The frontend belt then sees the specific code and
performs the diagnose -> assess conversion automatically.

Algorithm constraint: only rewrite when Nabla's code is LESS specific than
the patient's. This is conservative on purpose -- if Nabla emits a specific
code that doesn't match the patient's (e.g. patient has E11.65, provider
dictates ophthalmic complications, Nabla emits E11.36), we leave Nabla's
code alone; that's a genuinely different sub-condition, not a less-specific
parent.

PHI: this module receives clinical condition data. The helper itself returns
data; the caller is responsible for never logging condition codes or display
strings beyond aggregate counts.
"""

from __future__ import annotations

from hyperscribe.scribe.backend.models import CodingEntry, Condition
from hyperscribe.scribe.commands.problem_list_match import (
    ActivePatientCondition,
    icd10_normalize,
    icd10_is_unspecified_parent_of,
    prefer_patient_specific_codes,
)


# --- icd10_normalize ---


def test_icd10_normalize_removes_dot_and_uppercases() -> None:
    """A dotted lowercase ICD-10 string normalises to the dotless uppercase form
    we use as the comparison key throughout this module."""
    assert icd10_normalize("e11.65") == "E1165"


def test_icd10_normalize_already_dotless() -> None:
    """An already-dotless code is preserved (only case is normalised)."""
    assert icd10_normalize("e1165") == "E1165"


def test_icd10_normalize_strips_surrounding_whitespace() -> None:
    """Whitespace from carriage returns / pasted text is stripped."""
    assert icd10_normalize("  E11.65 ") == "E1165"


def test_icd10_normalize_empty_string() -> None:
    """An empty input produces an empty output (no crash)."""
    assert icd10_normalize("") == ""


# --- icd10_is_unspecified_parent_of ---


def test_unspecified_parent_e119_vs_e1165() -> None:
    """E11.9 (unspecified Type 2 DM) IS an unspecified parent of E11.65
    (Type 2 DM with hyperglycemia). This is the ticket's named case."""
    assert icd10_is_unspecified_parent_of("E11.9", "E11.65") is True


def test_unspecified_parent_dotless_codes() -> None:
    """Comparison works on dotless codes too -- inputs are normalised first."""
    assert icd10_is_unspecified_parent_of("E119", "E1165") is True


def test_unspecified_parent_different_family_rejected() -> None:
    """E11.9 (DM family) is NOT a parent of I10 (hypertension family)."""
    assert icd10_is_unspecified_parent_of("E11.9", "I10") is False


def test_unspecified_parent_specific_code_not_parent_of_specific() -> None:
    """E11.36 (DM w/ ophthalmic complications) is NOT a parent of E11.65
    (DM w/ hyperglycemia). Both are specific, sibling codes."""
    assert icd10_is_unspecified_parent_of("E11.36", "E11.65") is False


def test_unspecified_parent_same_code_rejected() -> None:
    """An identical code is not its own parent -- nothing to rewrite."""
    assert icd10_is_unspecified_parent_of("E11.65", "E11.65") is False


def test_unspecified_parent_root_only_e11() -> None:
    """A 3-char root code (e.g. E11 with no sub-classification) is the
    parent of any specific code in the family."""
    assert icd10_is_unspecified_parent_of("E11", "E11.65") is True


def test_unspecified_parent_z9989_unspecified_z_code() -> None:
    """Z99.89 (other dependence on enabling machines) ending in .89 is NOT
    treated as 'unspecified' -- only .9 / .9X / single-3-char-root qualify.

    Why this test exists: the algorithm cares about Nabla's tendency to emit
    .9 (the unspecified bucket within a 3-char family). Other endings carry
    their own clinical meaning and must not be rewritten."""
    assert icd10_is_unspecified_parent_of("Z99.89", "Z99.81") is False


def test_unspecified_parent_e119_vs_e11_root_rejected() -> None:
    """E11.9 is not 'more specific' than E11, so don't claim it as a parent
    of E11 itself. This rule prevents rewriting a Nabla E11.9 down to a
    patient-stored bare E11 (which would be a LOSS of specificity)."""
    assert icd10_is_unspecified_parent_of("E11.9", "E11") is False


# --- prefer_patient_specific_codes ---


def _icd(code: str, display: str = "") -> CodingEntry:
    return CodingEntry(system="ICD-10", code=code, display=display)


def _condition(code: str, display: str = "") -> Condition:
    return Condition(
        display=display or f"Condition {code}",
        clinical_status="active",
        coding=[_icd(code, display)],
    )


def _active(code: str, condition_id: str = "active-1", display: str = "") -> ActivePatientCondition:
    return ActivePatientCondition(
        condition_id=condition_id,
        code=code,
        display=display or f"Active {code}",
    )


def test_prefer_codes_rewrites_unspecified_parent_to_specific() -> None:
    """Ticket happy path: Nabla emitted E11.9 (unspecified DM), patient has
    E11.65 on the active problem list. The Nabla coding is rewritten to
    E11.65 so the frontend belt converts the diagnose to an assess linked
    to the existing condition."""
    nabla_conditions = [_condition("E11.9", "Type 2 diabetes mellitus without complications")]
    active = [_active("E11.65", "active-uuid-1", "Type 2 diabetes with hyperglycemia")]

    result = prefer_patient_specific_codes(nabla_conditions, active)

    assert len(result) == 1
    assert len(result[0].coding) == 1
    assert result[0].coding[0].code == "E11.65"
    assert result[0].coding[0].display == "Type 2 diabetes with hyperglycemia"


def test_prefer_codes_no_rewrite_when_nabla_specific_and_different() -> None:
    """Nabla emits E11.36 (DM w/ ophthalmic complications), patient has E11.65
    (DM w/ hyperglycemia) -- these are sibling specific codes, not parent/
    child. No rewrite: Nabla's code is the correct clinical answer."""
    nabla_conditions = [_condition("E11.36", "Type 2 diabetes w/ ophthalmic complications")]
    active = [_active("E11.65", "active-uuid-1", "Type 2 diabetes w/ hyperglycemia")]

    result = prefer_patient_specific_codes(nabla_conditions, active)

    assert result[0].coding[0].code == "E11.36"


def test_prefer_codes_no_rewrite_when_already_exact_match() -> None:
    """If Nabla already emitted the exact code on the active list, leave it
    alone -- the frontend belt handles diagnose -> assess from there."""
    nabla_conditions = [_condition("E11.65", "Type 2 DM w/ hyperglycemia")]
    active = [_active("E11.65", "active-uuid-1", "Type 2 DM w/ hyperglycemia")]

    result = prefer_patient_specific_codes(nabla_conditions, active)

    assert result[0].coding[0].code == "E11.65"


def test_prefer_codes_no_rewrite_when_no_family_match() -> None:
    """Nabla emits I10 (hypertension unspecified), patient only has E11.65
    (DM). No family overlap -- leave Nabla's code alone."""
    nabla_conditions = [_condition("I10", "Essential hypertension")]
    active = [_active("E11.65", "active-uuid-1", "Type 2 DM w/ hyperglycemia")]

    result = prefer_patient_specific_codes(nabla_conditions, active)

    assert result[0].coding[0].code == "I10"


def test_prefer_codes_empty_active_list_returns_input_unchanged() -> None:
    """Patient has no active conditions -- nothing to prefer. Input passes
    through unchanged. Regression guard for the empty-problem-list path."""
    nabla_conditions = [_condition("E11.9", "Type 2 DM unspecified")]

    result = prefer_patient_specific_codes(nabla_conditions, [])

    assert result is nabla_conditions or result[0].coding[0].code == "E11.9"


def test_prefer_codes_empty_nabla_conditions_returns_empty() -> None:
    """No Nabla conditions -- nothing to rewrite, result is empty.
    Regression guard for the silent-Nabla-response path."""
    active = [_active("E11.65", "active-uuid-1")]

    result = prefer_patient_specific_codes([], active)

    assert result == []


def test_prefer_codes_only_touches_icd10_codings() -> None:
    """A Nabla condition can carry multiple codings (ICD-10 + SNOMED, etc.).
    We only inspect/rewrite the ICD-10 coding; SNOMED and other systems are
    left alone."""
    nabla_conditions = [
        Condition(
            display="Type 2 diabetes",
            clinical_status="active",
            coding=[
                _icd("E11.9", "Type 2 DM unspecified"),
                CodingEntry(system="SNOMED", code="44054006", display="Diabetes mellitus type 2"),
            ],
        )
    ]
    active = [_active("E11.65", "active-uuid-1", "Type 2 DM w/ hyperglycemia")]

    result = prefer_patient_specific_codes(nabla_conditions, active)

    icd_codings = [c for c in result[0].coding if c.system == "ICD-10"]
    snomed_codings = [c for c in result[0].coding if c.system == "SNOMED"]
    assert icd_codings[0].code == "E11.65"
    assert snomed_codings[0].code == "44054006"
    assert snomed_codings[0].display == "Diabetes mellitus type 2"


def test_prefer_codes_multiple_patient_matches_picks_first_deterministically() -> None:
    """Patient has TWO active conditions in the same family (E11.65 AND E11.21),
    Nabla emits E11.9. The helper picks the first match deterministically --
    we do NOT silently pick at random. The ticket scope doesn't require
    sophisticated tie-breaking; document the first-wins rule and move on."""
    nabla_conditions = [_condition("E11.9", "Type 2 DM unspecified")]
    active = [
        _active("E11.65", "active-uuid-1", "Type 2 DM w/ hyperglycemia"),
        _active("E11.21", "active-uuid-2", "Type 2 DM w/ nephropathy"),
    ]

    result = prefer_patient_specific_codes(nabla_conditions, active)

    # First active condition in the family wins. Test pins this so a refactor
    # changing the order doesn't silently swap which code lands in the chart.
    assert result[0].coding[0].code == "E11.65"


def test_prefer_codes_active_condition_non_icd10_system_ignored() -> None:
    """An active condition coded only in SNOMED (no ICD-10) cannot be used
    as a hint -- the frontend belt matches on ICD-10. Treat it as if the
    condition were not on the active list for hint purposes."""
    nabla_conditions = [_condition("E11.9", "Type 2 DM unspecified")]
    active = [
        ActivePatientCondition(
            condition_id="active-uuid-1",
            code="",  # No ICD-10 code on this active condition
            display="Diabetes mellitus type 2",
        )
    ]

    result = prefer_patient_specific_codes(nabla_conditions, active)

    assert result[0].coding[0].code == "E11.9"


def test_prefer_codes_preserves_condition_display_and_clinical_status() -> None:
    """Rewriting the coding must not lose the parent Condition's display or
    clinical_status -- those drive the section-matching logic downstream."""
    nabla_conditions = [
        Condition(
            display="Type 2 diabetes",
            clinical_status="active",
            coding=[_icd("E11.9", "Type 2 DM unspecified")],
            corresponding_note_problem="Diabetes",
        )
    ]
    active = [_active("E11.65", "active-uuid-1", "Type 2 DM w/ hyperglycemia")]

    result = prefer_patient_specific_codes(nabla_conditions, active)

    assert result[0].display == "Type 2 diabetes"
    assert result[0].clinical_status == "active"
    assert result[0].corresponding_note_problem == "Diabetes"


def test_prefer_codes_does_not_mutate_input_list() -> None:
    """Pure function: the input list and its Condition objects must not be
    mutated. A caller relying on the original Nabla output for telemetry
    (raw response cached separately) shouldn't be surprised."""
    original = _condition("E11.9", "Type 2 DM unspecified")
    nabla_conditions = [original]
    active = [_active("E11.65", "active-uuid-1", "Type 2 DM w/ hyperglycemia")]

    prefer_patient_specific_codes(nabla_conditions, active)

    assert original.coding[0].code == "E11.9"
    assert original.coding[0].display == "Type 2 DM unspecified"


# --- DB-backed: _load_active_patient_conditions against the real ORM ---


def test_load_active_patient_conditions_real_orm_picks_icd10_active() -> None:
    """Integration: an active condition with both ICD-10 and SNOMED codings
    resolves through the real ORM to an ``ActivePatientCondition`` carrying
    the ICD-10 code.

    Why this matters: every other test for ``_load_active_patient_conditions``
    mocks ``ConditionModel.objects``. A typo in the filter chain
    (``.active().for_patient().prefetch_related().order_by()``) would pass
    those mocks but fail in production. This test pins the chain against
    a factory-backed real DB row.

    Also verifies the patient-scope filter (``for_patient``) actually
    rejects a condition on a *different* patient -- a HIPAA-relevant guard.
    """
    import datetime

    from canvas_sdk.test_utils import factories
    from canvas_sdk.v1.data.condition import Condition, ConditionCoding

    from hyperscribe.scribe.api.session_view import _load_active_patient_conditions

    patient_target = factories.PatientFactory.create()
    patient_other = factories.PatientFactory.create()
    user = factories.CanvasUserFactory.create()

    target_condition = Condition.objects.create(
        patient=patient_target,
        deleted=False,
        onset_date=datetime.date(2024, 6, 1),
        resolution_date=datetime.date(2099, 12, 31),
        clinical_status="active",
        surgical=False,
        committer=user,
    )
    # SNOMED first, ICD-10 second -- the helper must still pick the ICD-10
    # coding regardless of insertion order.
    ConditionCoding.objects.create(
        condition=target_condition,
        system="http://snomed.info/sct",
        code="44054006",
        display="Diabetes mellitus type 2",
    )
    ConditionCoding.objects.create(
        condition=target_condition,
        system="ICD-10",
        code="E1165",
        display="Type 2 diabetes mellitus with hyperglycemia",
    )

    # A condition on a different patient -- must not appear in the result.
    other_condition = Condition.objects.create(
        patient=patient_other,
        deleted=False,
        onset_date=datetime.date(2023, 1, 1),
        resolution_date=datetime.date(2099, 12, 31),
        clinical_status="active",
        surgical=False,
        committer=user,
    )
    ConditionCoding.objects.create(
        condition=other_condition,
        system="ICD-10",
        code="I10",
        display="Essential hypertension",
    )

    result = _load_active_patient_conditions(patient_target.id)

    assert len(result) == 1, (
        "Expected exactly one entry for the target patient -- "
        "the other patient's condition must be filtered out by for_patient()."
    )
    assert result[0].condition_id == str(target_condition.id)
    assert result[0].code == "E1165"
    assert result[0].display == "Type 2 diabetes mellitus with hyperglycemia"


def test_load_active_patient_conditions_real_orm_excludes_resolved() -> None:
    """Integration: a resolved condition (clinical_status != "active") is
    excluded by the ``.active()`` queryset chain.

    Without this guard, a patient whose Type 2 DM was resolved would still
    get their old E11.65 used as a hint to rewrite the next encounter's
    Nabla code -- which would be a clinical regression."""
    import datetime

    from canvas_sdk.test_utils import factories
    from canvas_sdk.v1.data.condition import Condition, ConditionCoding

    from hyperscribe.scribe.api.session_view import _load_active_patient_conditions

    patient = factories.PatientFactory.create()
    user = factories.CanvasUserFactory.create()

    resolved = Condition.objects.create(
        patient=patient,
        deleted=False,
        onset_date=datetime.date(2020, 1, 1),
        resolution_date=datetime.date(2023, 12, 31),
        clinical_status="resolved",
        surgical=False,
        committer=user,
    )
    ConditionCoding.objects.create(
        condition=resolved,
        system="ICD-10",
        code="E1165",
        display="Type 2 diabetes mellitus with hyperglycemia",
    )

    result = _load_active_patient_conditions(patient.id)

    assert result == [], "Resolved conditions must not be returned by the active() chain."
