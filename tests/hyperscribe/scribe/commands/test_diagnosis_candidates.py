"""Tests for the grounded ICD-10 candidate engine (``diagnosis_candidates``).

The engine replaces the old first-match-wins code pick in the A&P belt. The
canonical regression is the Jodie Foster note: Nabla emitted both ``R45.851``
"Suicidal ideations" (a Chapter-18 symptom code, listed first) and ``F33.1`` for
a single "Major depressive disorder, recurrent, moderate to severe" block. The
old belt stamped R45.851 and orphaned F33.1; the engine must rank F33.1 first and
never discard R45.851.

These tests are pure — the only injected dependency is a fake ``science_search``
callable returning ``Icd10Condition``-shaped objects.
"""

from __future__ import annotations

from hyperscribe.scribe.commands.diagnosis_candidates import (
    MAX_SURFACED_SUGGESTIONS,
    CandidateSource,
    DiagnosisCandidate,
    PatientConditionSnapshot,
    _overlap_bucket,
    assemble_block_candidates,
    build_block_candidates,
    expand_unspecified,
    is_unspecified_code,
    provenance_label,
    rank_candidates,
    surface_candidates,
)
from hyperscribe.structures.icd10_condition import Icd10Condition

MDD_HEADER = "Major depressive disorder, recurrent, moderate to severe"


def _nabla_block(*codings: tuple[str, str]) -> list[dict]:
    """One Nabla condition dict whose ``coding`` is the given (code, display) pairs."""
    return [{"display": "", "coding": [{"code": code, "display": display} for code, display in codings]}]


# The Jodie Foster ordering: symptom code first, definitive code second.
_JODIE_NABLA = _nabla_block(
    ("R45.851", "Suicidal ideations"),
    ("F33.1", "Major depressive disorder, recurrent, moderate"),
)


def test_f331_beats_r45851_no_chart() -> None:
    result = build_block_candidates("apblock-0", MDD_HEADER, _JODIE_NABLA, chart=[])
    assert result.chosen is not None
    assert result.chosen.code == "F331"
    assert result.ambiguous is False


def test_f331_beats_r45851_with_active_f33() -> None:
    chart = [
        PatientConditionSnapshot(
            condition_id="cond-1",
            code="F33.1",
            display="Major depressive disorder, recurrent, moderate",
            system="ICD-10",
            clinical_status="active",
            onset_date="2010-01-01",
            resolution_date="",
        )
    ]
    result = build_block_candidates("apblock-0", MDD_HEADER, _JODIE_NABLA, chart=chart)
    assert result.chosen is not None
    assert result.chosen.code == "F331"
    assert result.chosen.source == CandidateSource.ACTIVE_PROBLEM
    # condition_id flows through so the diagnose->assess flip stays eligible.
    assert result.chosen.condition_id == "cond-1"


def test_no_orphan_symptom_code_survives_as_candidate() -> None:
    result = build_block_candidates("apblock-0", MDD_HEADER, _JODIE_NABLA, chart=[])
    codes = {candidate.code for candidate in result.candidates}
    # F33.1 wins, but R45.851 is NOT discarded — it remains a (lower) candidate.
    assert "F331" in codes
    assert "R45851" in codes


def test_ambiguous_two_definitive_codes_tie() -> None:
    # Two genuinely different definitive codes, both overlapping the header equally.
    nabla = _nabla_block(
        ("G44.1", "Vascular headache"),
        ("G44.209", "Tension-type headache"),
    )
    result = build_block_candidates("apblock-0", "Headache", nabla, chart=[])
    assert result.chosen is None
    assert result.ambiguous is True
    # Both surfaced for the provider to choose.
    codes = {candidate.code for candidate in result.candidates}
    assert {"G441", "G44209"} <= codes


def test_incidental_symptom_code_is_ambiguous() -> None:
    # An R-code that does NOT match the header (incidental — the Jodie case where
    # Nabla only emitted "Suicidal ideations" for a depression block) is surfaced,
    # never auto-stamped as the diagnosis.
    nabla = _nabla_block(("R45.851", "Suicidal ideations"))
    result = build_block_candidates("apblock-0", MDD_HEADER, nabla, chart=[])
    assert result.chosen is None
    assert result.ambiguous is True


def test_matching_symptom_code_is_applied() -> None:
    # A symptom code that IS the documented problem (full header overlap) stays a
    # legitimate primary diagnosis — auto-applied, not flagged.
    nabla = _nabla_block(("R19.7", "Diarrhea, unspecified"))
    result = build_block_candidates("apblock-0", "Diarrhea, unspecified", nabla, chart=[])
    assert result.chosen is not None
    assert result.chosen.code == "R197"
    assert result.ambiguous is False


def test_charted_specific_beats_nabla_unspecified() -> None:
    # Nabla emits the unspecified parent; the patient's resolved-but-specific code wins.
    nabla = _nabla_block(("E11.9", "Type 2 diabetes mellitus without complications"))
    chart = [
        PatientConditionSnapshot(
            condition_id="cond-9",
            code="E11.65",
            display="Type 2 diabetes mellitus with hyperglycemia",
            system="ICD-10",
            clinical_status="resolved",
            onset_date="2015-01-01",
            resolution_date="2021-06-01",
        )
    ]
    result = build_block_candidates("apblock-0", "Type 2 diabetes mellitus", nabla, chart=chart)
    assert result.chosen is not None
    assert result.chosen.code == "E1165"
    assert result.chosen.source == CandidateSource.PRIOR_CONDITION
    # Prior conditions never carry a flip-eligible condition_id (no SDK reactivation).
    assert result.chosen.condition_id == ""


def test_provenance_labels() -> None:
    active = DiagnosisCandidate(code="F331", raw_code="F33.1", display="", source=CandidateSource.ACTIVE_PROBLEM)
    resolved = DiagnosisCandidate(
        code="F331",
        raw_code="F33.1",
        display="",
        source=CandidateSource.PRIOR_CONDITION,
        clinical_status="resolved",
        resolution_date="2021-06-01",
    )
    remission = DiagnosisCandidate(
        code="F331", raw_code="F33.1", display="", source=CandidateSource.PRIOR_CONDITION, clinical_status="remission"
    )
    nabla = DiagnosisCandidate(code="F331", raw_code="F33.1", display="", source=CandidateSource.NABLA)
    science = DiagnosisCandidate(code="F331", raw_code="F33.1", display="", source=CandidateSource.SCIENCE_SEARCH)
    more = DiagnosisCandidate(code="G4701", raw_code="G47.01", display="", source=CandidateSource.MORE_SPECIFIC)
    assert provenance_label(active) == "Active problem"
    # Every non-active status collapses to one catch-all tag.
    assert provenance_label(resolved) == "Past condition"
    assert provenance_label(remission) == "Past condition"
    assert provenance_label(nabla) == "Detected in note"
    assert provenance_label(science) == "ICD-10 search"
    assert provenance_label(more) == "More specific option"


def test_is_unspecified_code() -> None:
    # Display text is the reliable signal.
    assert is_unspecified_code("G47.00", "Insomnia, unspecified") is True
    assert is_unspecified_code("F33.9", "Major depressive disorder, recurrent, unspecified") is True
    assert is_unspecified_code("G4700") is False  # no display -> numeric "00" not flagged
    # Bare 3-char rubric (never independently billable).
    assert is_unspecified_code("E03") is True
    # ".9"/"without X" default codes are NOT unspecified (display doesn't say so) — the
    # relaxed rule avoids forcing needless refinement picks on these standard codes.
    assert is_unspecified_code("E11.9", "Type 2 diabetes mellitus without complications") is False
    assert is_unspecified_code("K21.9", "Gastro-esophageal reflux disease without esophagitis") is False
    assert is_unspecified_code("F33.1", "Major depressive disorder, recurrent, moderate") is False


def test_expand_unspecified_offers_specific_siblings() -> None:
    chosen = DiagnosisCandidate(
        code="G4700", raw_code="G47.00", display="Insomnia, unspecified", source=CandidateSource.NABLA
    )

    def fake_search(expressions: list[str]) -> list[Icd10Condition]:
        assert expressions == ["G47"]  # searched by family root
        return [
            Icd10Condition(code="G4700", label="Insomnia, unspecified"),
            Icd10Condition(code="G4701", label="Insomnia due to medical condition"),
            Icd10Condition(code="G4709", label="Other insomnia"),
            # Same 3-char family but a DIFFERENT sub-category — must be excluded
            # (these are what showed up as noise in UAT).
            Icd10Condition(code="G4733", label="Obstructive sleep apnea"),
            Icd10Condition(code="G4763", label="Sleep related bruxism"),
        ]

    children = expand_unspecified(chosen, fake_search)
    codes = {child.code for child in children}
    assert "G4700" not in codes  # the unspecified bucket itself is excluded
    assert {"G4701", "G4709"} == codes  # only the G47.0x insomnia sub-category
    assert "G4733" not in codes and "G4763" not in codes  # apnea/bruxism filtered out
    assert all(child.source == CandidateSource.MORE_SPECIFIC for child in children)


def test_expand_unspecified_drops_non_leaf_and_duplicate() -> None:
    # E78.4 is a non-billable category parent of E78.41/E78.49 (and shares a display
    # with E78.49) — it must not be offered as a selectable refinement.
    chosen = DiagnosisCandidate(
        code="E785", raw_code="E78.5", display="Hyperlipidemia, unspecified", source=CandidateSource.NABLA
    )

    def fake_search(_expressions: list[str]) -> list[Icd10Condition]:
        return [
            Icd10Condition(code="E784", label="Other hyperlipidemia"),
            Icd10Condition(code="E7849", label="Other hyperlipidemia"),
            Icd10Condition(code="E782", label="Mixed hyperlipidemia"),
        ]

    codes = {c.code for c in expand_unspecified(chosen, fake_search)}
    assert "E784" not in codes  # non-leaf parent dropped
    assert codes == {"E7849", "E782"}


def test_science_fallback_recovers_code_via_body_synonym() -> None:
    # Nabla emitted nothing for the block; the ICD display ("Impingement syndrome")
    # doesn't match the header ("tendinitis") but the assessment body says "impingement".
    header = "Right rotator cuff tendinitis"
    context = f"{header}\nDiagnosis consistent with rotator cuff tendinitis or impingement."

    def fake_search(expressions: list[str]) -> list[Icd10Condition]:
        if any("impingement" in expression for expression in expressions):
            return [Icd10Condition(code="M7541", label="Impingement syndrome of right shoulder")]
        return []

    result = build_block_candidates(
        "apblock-0", header, nabla_for_block=[], chart=[], science_search=fake_search, context_text=context
    )
    codes = {c.code for c in result.candidates}
    assert "M7541" in codes  # recovered via the body synonym
    assert result.candidates[0].code == "M7541"  # ranked first by full-context overlap


def test_expand_unspecified_scopes_four_char_code_to_family_root() -> None:
    # Fix: a 4-char unspecified code (E78.5 "Hyperlipidemia, unspecified") offers its
    # 3-char-root siblings — previously the "E785" sub-bucket found nothing.
    chosen = DiagnosisCandidate(
        code="E785", raw_code="E78.5", display="Hyperlipidemia, unspecified", source=CandidateSource.NABLA
    )

    def fake_search(expressions: list[str]) -> list[Icd10Condition]:
        assert expressions == ["E78"]
        return [
            Icd10Condition(code="E782", label="Mixed hyperlipidemia"),
            Icd10Condition(code="E781", label="Pure hyperglyceridemia"),
        ]

    assert {c.code for c in expand_unspecified(chosen, fake_search)} == {"E782", "E781"}


def test_expand_unspecified_ranks_by_note_context() -> None:
    # The refinement the note documents ("moderate") leads over other siblings.
    chosen = DiagnosisCandidate(
        code="F329",
        raw_code="F32.9",
        display="Major depressive disorder, single episode, unspecified",
        source=CandidateSource.NABLA,
    )

    def fake_search(_expressions: list[str]) -> list[Icd10Condition]:
        return [
            Icd10Condition(code="F320", label="Major depressive disorder, single episode, mild"),
            Icd10Condition(code="F321", label="Major depressive disorder, single episode, moderate"),
            Icd10Condition(code="F322", label="Major depressive disorder, single episode, severe"),
        ]

    children = expand_unspecified(chosen, fake_search, context_text="Moderate depression, PHQ-9 12.")
    assert children[0].code == "F321"


def test_science_search_only_is_never_auto_applied() -> None:
    # No chart, no Nabla coding -> science fallback fires but stays ambiguous.
    def fake_search(expressions: list[str]) -> list[Icd10Condition]:
        return [Icd10Condition(code="J069", label="Acute upper respiratory infection, unspecified")]

    result = build_block_candidates(
        "apblock-0", "Upper respiratory infection", nabla_for_block=[], chart=[], science_search=fake_search
    )
    assert result.chosen is None
    assert result.ambiguous is True
    assert any(c.source == CandidateSource.SCIENCE_SEARCH for c in result.candidates)


def test_no_candidates_is_uncoded_not_ambiguous() -> None:
    result = build_block_candidates("apblock-0", "Some freetext header", nabla_for_block=[], chart=[])
    assert result.chosen is None
    assert result.ambiguous is False
    assert result.candidates == []


def test_assemble_dedupes_to_highest_trust_source() -> None:
    # Same code from Nabla and the active problem list -> keep the active one.
    nabla = _nabla_block(("F33.1", "Major depressive disorder, recurrent, moderate"))
    chart = [
        PatientConditionSnapshot(
            condition_id="cond-1",
            code="F33.1",
            display="Major depressive disorder, recurrent, moderate",
            system="ICD-10",
            clinical_status="active",
            onset_date="",
            resolution_date="",
        )
    ]
    candidates = assemble_block_candidates(MDD_HEADER, nabla, chart)
    f331 = [c for c in candidates if c.code == "F331"]
    assert len(f331) == 1
    assert f331[0].source == CandidateSource.ACTIVE_PROBLEM


def test_rank_orders_definitive_above_symptom() -> None:
    candidates = assemble_block_candidates(MDD_HEADER, _JODIE_NABLA, chart=[])
    ranked = rank_candidates(MDD_HEADER, candidates)
    assert ranked[0].code == "F331"
    assert ranked[-1].code == "R45851"


def test_cross_family_chart_vs_note_conflict_is_ambiguous() -> None:
    # UAT regression: the patient's stale active problem F32.1 ("single episode")
    # must NOT auto-override the encounter's documented F33.1 ("recurrent"). Different
    # ICD families + the note matches F33.1 better -> surface both, let provider pick.
    nabla = _nabla_block(("F33.1", "Major depressive disorder, recurrent, moderate"))
    chart = [
        PatientConditionSnapshot(
            condition_id="cond-mdd",
            code="F32.1",
            display="Major depressive disorder, single episode, moderate",
            system="ICD-10",
            clinical_status="active",
            onset_date="2002-01-01",
            resolution_date="",
        )
    ]
    result = build_block_candidates("apblock-0", MDD_HEADER, nabla, chart=chart)
    assert result.chosen is None
    assert result.ambiguous is True
    by_code = {c.code: c for c in result.candidates}
    assert {"F321", "F331"} <= set(by_code)
    assert provenance_label(by_code["F321"]) == "Active problem"
    assert provenance_label(by_code["F331"]) == "Detected in note"


def test_same_family_active_still_auto_applies() -> None:
    # Guard against over-triggering: a same-family active code (more specific) still
    # wins over Nabla's unspecified one — this is continuity, not a conflict.
    nabla = _nabla_block(("E11.9", "Type 2 diabetes mellitus without complications"))
    chart = [
        PatientConditionSnapshot(
            condition_id="cond-dm",
            code="E11.65",
            display="Type 2 diabetes mellitus with hyperglycemia",
            system="ICD-10",
            clinical_status="active",
            onset_date="2018-01-01",
            resolution_date="",
        )
    ]
    result = build_block_candidates("apblock-0", "Type 2 diabetes mellitus", nabla, chart=chart)
    assert result.chosen is not None
    assert result.chosen.code == "E1165"
    assert result.ambiguous is False


def test_provenance_labels_full_status_matrix() -> None:
    def prior(status: str) -> DiagnosisCandidate:
        return DiagnosisCandidate(
            code="F331", raw_code="F33.1", display="", source=CandidateSource.PRIOR_CONDITION, clinical_status=status
        )

    # Every non-active clinical status maps to the single "Past condition" tag.
    assert provenance_label(prior("relapse")) == "Past condition"
    assert provenance_label(prior("investigative")) == "Past condition"
    assert provenance_label(prior("resolved")) == "Past condition"
    assert provenance_label(prior("")) == "Past condition"
    # Unknown source -> empty label.
    assert provenance_label(DiagnosisCandidate(code="F331", raw_code="F33.1", display="", source="mystery")) == ""


def _cand(code: str, raw: str, display: str, source: str = CandidateSource.NABLA) -> DiagnosisCandidate:
    return DiagnosisCandidate(code=code, raw_code=raw, display=display, source=source)


def test_surface_candidates_drops_symptom_when_definitive_exists() -> None:
    cands = [
        _cand("F331", "F33.1", "MDD recurrent moderate"),
        _cand("R45851", "R45.851", "Suicidal ideations"),
    ]
    # The incidental symptom code is not offered as a diagnosis to pick.
    assert [c.code for c in surface_candidates(cands)] == ["F331"]


def test_surface_candidates_keeps_symptom_when_it_is_the_only_option() -> None:
    assert [c.code for c in surface_candidates([_cand("R197", "R19.7", "Diarrhea, unspecified")])] == ["R197"]


def test_surface_candidates_caps_length() -> None:
    cands = [_cand(f"E03{i}", f"E03.{i}", f"opt {i}", CandidateSource.MORE_SPECIFIC) for i in range(9)]
    assert len(surface_candidates(cands)) == MAX_SURFACED_SUGGESTIONS


def test_overlap_bucket_partial() -> None:
    assert _overlap_bucket("left knee pain swelling", "knee pain stiffness") == 1
    assert _overlap_bucket("Headache", "Headache") == 2
    assert _overlap_bucket("Diabetes", "Suicidal ideations") == 0


def test_assemble_skips_malformed_codings_and_snapshots() -> None:
    nabla = [
        {
            "display": "",
            "coding": [
                {"code": "", "display": "blank code"},  # skipped: no code
                {"display": "no code key"},  # skipped: no code
                {"code": "F33.1", "display": "Major depressive disorder, recurrent, moderate"},
            ],
        }
    ]
    chart = [
        PatientConditionSnapshot("c0", "", "Empty code", "ICD-10", "active", "", ""),  # skipped: no code
        PatientConditionSnapshot("c1", "K21.9", "GERD", "ICD-10", "active", "", ""),  # skipped: no match
    ]
    candidates = assemble_block_candidates(MDD_HEADER, nabla, chart)
    codes = {c.code for c in candidates}
    assert codes == {"F331"}


def test_assemble_survives_science_outage() -> None:
    def boom(_expressions: list[str]) -> list:
        raise RuntimeError("science down")

    result = build_block_candidates("apblock-0", "Sciatica", nabla_for_block=[], chart=[], science_search=boom)
    assert result.candidates == []
    assert result.chosen is None
    assert result.ambiguous is False


def test_expand_unspecified_survives_science_outage_and_filters_family() -> None:
    chosen = DiagnosisCandidate(
        code="E039", raw_code="E03.9", display="Hypothyroidism, unspecified", source=CandidateSource.NABLA
    )

    def boom(_expressions: list[str]) -> list:
        raise RuntimeError("science down")

    assert expand_unspecified(chosen, boom) == []
    assert expand_unspecified(chosen, None) == []

    def cross_family(_expressions: list[str]) -> list[Icd10Condition]:
        return [
            Icd10Condition(code="E030", label="Postsurgical hypothyroidism"),  # same family, specific -> kept
            Icd10Condition(code="E1165", label="Type 2 diabetes with hyperglycemia"),  # other family -> dropped
        ]

    children = expand_unspecified(chosen, cross_family)
    assert {c.code for c in children} == {"E030"}
