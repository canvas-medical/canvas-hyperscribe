from typing import Any
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.ap_split import (
    _build_active_condition_icd10_index,
    _normalize_icd10,
    match_condition,
    parse_ap_blocks,
    significant_words,
    split_plan_into_diagnoses,
    word_overlap,
)


# --- parse_ap_blocks ---


def test_parse_ap_blocks_empty() -> None:
    assert parse_ap_blocks("") == []


def test_parse_ap_blocks_none_text() -> None:
    # The function should treat None-ish empty string the same.
    assert parse_ap_blocks("") == []


def test_parse_ap_blocks_single_header_no_body() -> None:
    blocks = parse_ap_blocks("Migraine without aura")
    assert len(blocks) == 1
    assert blocks[0].header == "Migraine without aura"
    assert blocks[0].body == []


def test_parse_ap_blocks_header_with_bullets() -> None:
    text = "Migraine without aura\n- Start sumatriptan 50mg\n- Reduce screen time"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].header == "Migraine without aura"
    assert len(blocks[0].body) == 2
    assert blocks[0].body[0] == "- Start sumatriptan 50mg"
    assert blocks[0].body[1] == "- Reduce screen time"


def test_parse_ap_blocks_multiple_blocks() -> None:
    text = "Migraine without aura\n- Start sumatriptan\n\nHypertension\n- Continue lisinopril\n- Monitor BP"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].header == "Migraine without aura"
    assert blocks[0].body == ["- Start sumatriptan"]
    assert blocks[1].header == "Hypertension"
    assert len(blocks[1].body) == 2


def test_parse_ap_blocks_multiline_header() -> None:
    text = "Migraine without aura\nLikely triggered by stress\n- Start sumatriptan"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].header == "Migraine without aura\nLikely triggered by stress"
    assert blocks[0].body == ["- Start sumatriptan"]


def test_parse_ap_blocks_orphan_bullets() -> None:
    text = "- Something without a header"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 1
    assert blocks[0].header == ""
    assert blocks[0].body == ["- Something without a header"]


def test_parse_ap_blocks_blank_lines_between() -> None:
    text = "Block1\n\n\nBlock2"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 2
    assert blocks[0].header == "Block1"
    assert blocks[1].header == "Block2"


def test_parse_ap_blocks_bullet_markers() -> None:
    """Different bullet styles are recognized."""
    text = "Header\n* star bullet\n\u2022 unicode bullet"
    blocks = parse_ap_blocks(text)
    assert len(blocks) == 1
    assert len(blocks[0].body) == 2


# --- significant_words ---


def test_significant_words_filters_stop_words() -> None:
    words = significant_words("the quick brown fox and a lazy dog")
    assert "the" not in words
    assert "and" not in words
    assert "a" not in words
    assert "quick" in words
    assert "brown" in words


def test_significant_words_filters_medical_qualifiers() -> None:
    words = significant_words("Diarrhea, unspecified")
    assert "unspecified" not in words
    assert "diarrhea" in words
    words = significant_words("Other specified anxiety disorders")
    assert "other" not in words
    assert "specified" not in words
    assert "anxiety" in words
    assert "disorders" in words


def test_significant_words_filters_short() -> None:
    words = significant_words("I am ok")
    assert "i" not in words  # single char after lowering
    assert "am" in words  # 2 chars is ok
    assert "ok" in words


def test_significant_words_strips_punctuation() -> None:
    words = significant_words("Headache, persistent")
    assert "headache" in words
    assert "persistent" in words


# --- word_overlap ---


def test_word_overlap_identical() -> None:
    assert word_overlap("chronic headache", "chronic headache") == 1.0


def test_word_overlap_partial() -> None:
    score = word_overlap("chronic daily headache", "headache disorder")
    assert score > 0.0


def test_word_overlap_no_match() -> None:
    assert word_overlap("migraine", "diabetes mellitus") == 0.0


def test_word_overlap_empty() -> None:
    assert word_overlap("", "something") == 0.0
    assert word_overlap("something", "") == 0.0


# --- match_condition ---


def test_match_condition_exact_substring() -> None:
    conditions = [
        {"display": "Headache", "coding": [{"code": "R51", "display": "Headache"}]},
        {"display": "Hypertension", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
    ]
    result = match_condition("Headache", conditions)
    assert result is not None
    assert result["display"] == "Headache"


def test_match_condition_substring_in_coding_display() -> None:
    conditions = [
        {"display": "HTN", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
    ]
    result = match_condition("Essential hypertension, well controlled", conditions)
    assert result is not None
    assert result["display"] == "HTN"


def test_match_condition_header_within_display() -> None:
    conditions = [
        {"display": "Migraine without aura, chronic", "coding": []},
    ]
    result = match_condition("Migraine without aura", conditions)
    assert result is not None


def test_match_condition_word_overlap_pass() -> None:
    conditions = [
        {"display": "Type 2 diabetes mellitus", "coding": [{"code": "E11", "display": "Type 2 diabetes"}]},
    ]
    result = match_condition("Diabetes type 2", conditions)
    assert result is not None


def test_match_condition_no_match() -> None:
    conditions = [
        {"display": "Headache", "coding": [{"code": "R51", "display": "Headache"}]},
    ]
    result = match_condition("Lower back pain", conditions)
    assert result is None


def test_match_condition_empty_conditions() -> None:
    assert match_condition("Headache", []) is None


def test_match_condition_empty_header() -> None:
    conditions = [{"display": "Headache", "coding": []}]
    assert match_condition("", conditions) is None


# --- split_plan_into_diagnoses ---


def test_split_plan_into_diagnoses_basic() -> None:
    commands = [
        {"command_type": "rfv", "data": {"comment": "Pain"}, "section_key": "chief_complaint"},
        {
            "command_type": "plan",
            "data": {"narrative": "Migraine\n- Start sumatriptan\n\nHypertension\n- Continue lisinopril"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Migraine", "coding": [{"code": "G43.909", "display": "Migraine, unspecified"}]},
            {"display": "Hypertension", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 3  # rfv + 2 diagnose
    assert updated[0]["command_type"] == "rfv"
    assert updated[1]["command_type"] == "diagnose"
    assert updated[1]["data"]["icd10_code"] == "G43.909"
    assert updated[1]["data"]["accepted"] is False
    assert updated[2]["command_type"] == "diagnose"
    assert updated[2]["data"]["icd10_code"] == "I10"
    assert unmatched == []


def test_split_plan_into_diagnoses_unmatched() -> None:
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Migraine\n- Start sumatriptan"},
            "section_key": "assessment_and_plan",
        },
    ]
    extra_condition = {"display": "Diabetes", "coding": [{"code": "E11", "display": "Type 2 diabetes"}]}
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Migraine", "coding": [{"code": "G43.909", "display": "Migraine"}]},
            extra_condition,
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["command_type"] == "diagnose"
    assert len(unmatched) == 1
    assert unmatched[0] is extra_condition


def test_split_plan_into_diagnoses_no_plan_command() -> None:
    commands = [
        {"command_type": "rfv", "data": {"comment": "Pain"}, "section_key": "chief_complaint"},
    ]
    updated, unmatched = split_plan_into_diagnoses(commands, {"assessment_and_plan": []})
    assert updated == commands
    assert unmatched == []


def test_split_plan_into_diagnoses_empty_narrative() -> None:
    commands = [
        {"command_type": "plan", "data": {"narrative": ""}, "section_key": "assessment_and_plan"},
    ]
    updated, unmatched = split_plan_into_diagnoses(commands, {"assessment_and_plan": []})
    assert updated == commands
    assert unmatched == []


def test_split_plan_into_diagnoses_no_icd_code() -> None:
    """When a condition has no coding, the diagnose block is created without an ICD code."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Unknown condition\n- Monitor"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions: dict[str, list[dict[str, object]]] = {"assessment_and_plan": []}
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["command_type"] == "diagnose"
    assert updated[0]["data"]["icd10_code"] is None
    assert updated[0]["data"]["accepted"] is False


def test_split_plan_preserves_other_commands() -> None:
    """Commands before and after the plan command are preserved."""
    commands = [
        {"command_type": "rfv", "data": {"comment": "Pain"}, "section_key": "chief_complaint"},
        {
            "command_type": "plan",
            "data": {"narrative": "Migraine\n- Sumatriptan"},
            "section_key": "assessment_and_plan",
        },
        {"command_type": "hpi", "data": {"narrative": "Headache"}, "section_key": "history_of_present_illness"},
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Migraine", "coding": [{"code": "G43", "display": "Migraine"}]},
        ],
    }
    updated, _ = split_plan_into_diagnoses(commands, section_conditions)
    assert updated[0]["command_type"] == "rfv"
    assert updated[1]["command_type"] == "diagnose"
    assert updated[2]["command_type"] == "hpi"


def test_split_plan_uses_plan_section_key() -> None:
    """Works with section_key='plan' as well as 'assessment_and_plan'."""
    commands = [
        {"command_type": "plan", "data": {"narrative": "Headache\n- Rest"}, "section_key": "plan"},
    ]
    section_conditions = {
        "plan": [{"display": "Headache", "coding": [{"code": "R51", "display": "Headache"}]}],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["command_type"] == "diagnose"
    assert updated[0]["section_key"] == "plan"
    assert unmatched == []


def test_split_plan_corresponding_note_problem() -> None:
    """When corresponding_note_problem is set, it takes priority over fuzzy matching."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Acute upper respiratory infection\n- Rest and fluids"},
            "section_key": "assessment_and_plan",
        },
    ]
    # The display text does NOT match the header, but corresponding_note_problem does.
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "URI",
                "coding": [{"code": "J06.9", "display": "Acute upper respiratory infection, unspecified"}],
                "corresponding_note_problem": "Acute upper respiratory infection",
            },
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["data"]["icd10_code"] == "J06.9"
    assert updated[0]["data"]["accepted"] is False


def test_unspecified_does_not_cause_false_match() -> None:
    """'unspecified' should not cause unrelated conditions to match via word overlap."""
    conditions = [
        {
            "display": "Major depressive disorder",
            "coding": [{"code": "F32.9", "display": "Major depressive disorder, single episode, unspecified"}],
        },
    ]
    assert match_condition("Diarrhea unspecified", conditions) is None
    assert match_condition("Constipation unspecified", conditions) is None
    assert match_condition("Unspecified disorder of adnexa", conditions) is None


def test_split_plan_corresponding_note_problem_prevents_wrong_match() -> None:
    """corresponding_note_problem prevents unrelated conditions from matching via word overlap."""
    commands = [
        {
            "command_type": "plan",
            "data": {
                "narrative": (
                    "Diarrhea, unspecified\n- Monitor hydration\n\n"
                    "Sarcoidosis, unspecified\n- Continue current treatment"
                )
            },
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Diarrhea, unspecified",
                "coding": [{"code": "R19.7", "display": "Diarrhea, unspecified"}],
                "corresponding_note_problem": "Diarrhea, unspecified",
            },
            {
                "display": "Sarcoidosis, unspecified",
                "coding": [{"code": "D86.9", "display": "Sarcoidosis, unspecified"}],
                "corresponding_note_problem": "Sarcoidosis, unspecified",
            },
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 2
    # Diarrhea gets R19.7, NOT D86.9
    assert updated[0]["data"]["icd10_code"] == "R19.7"
    # Sarcoidosis gets D86.9
    assert updated[1]["data"]["icd10_code"] == "D86.9"


def test_split_plan_corresponding_note_problem_case_insensitive() -> None:
    """corresponding_note_problem matching is case-insensitive."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "acute upper respiratory infection\n- Rest and fluids"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "URI",
                "coding": [{"code": "J06.9", "display": "Acute upper respiratory infection, unspecified"}],
                "corresponding_note_problem": "Acute Upper Respiratory Infection",
            },
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["data"]["icd10_code"] == "J06.9"


def test_split_plan_corresponding_note_problem_strips_whitespace() -> None:
    """corresponding_note_problem matching ignores leading/trailing whitespace."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Headache\n- Take ibuprofen"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Headache",
                "coding": [{"code": "R51.9", "display": "Headache, unspecified"}],
                "corresponding_note_problem": "  Headache  ",
            },
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["data"]["icd10_code"] == "R51.9"


# --- KOALA-5635: condition_id stamping on diagnose proposals ---


def _patch_active_conditions_values_list(rows: list[tuple[str, str | None, str | None]]) -> Any:
    """Patch the ConditionModel.objects.active().for_patient(...).values_list(...) chain.

    Round-2 (KOALA-5635): the helper was refactored from a
    ``prefetch_related("codings")`` + full-ORM iteration to a
    ``.values_list("id", "codings__code", "codings__system")`` shape per
    CLAUDE.md's "never fetch full objects from the database if you only
    need a couple properties." The new chain is:

        ConditionModel.objects.active().for_patient(...).values_list(
            "id", "codings__code", "codings__system",
        )

    which yields one row per (condition, coding) pair (LEFT JOIN over
    codings). Conditions without codings surface with NULL code/system
    and get skipped by the helper's ``not coding_code`` guard.
    """
    chain = MagicMock()
    chain.active.return_value = chain
    chain.for_patient.return_value = chain
    chain.values_list.return_value = rows  # iterable yields tuples
    return patch(
        "canvas_sdk.v1.data.condition.Condition.objects",
        chain,
    )


def test_normalize_icd10_strips_dots_and_uppercases() -> None:
    """Mirrors the frontend handleInsert match step in summary.js."""
    assert _normalize_icd10("i10") == "I10"
    assert _normalize_icd10("E11.9") == "E119"
    assert _normalize_icd10("e11.9") == "E119"
    assert _normalize_icd10("") == ""
    assert _normalize_icd10(None) == ""


def test_build_active_condition_icd10_index_happy_path() -> None:
    """Build a {normalized_icd10 → condition_id} index for the note's patient.

    Round-2 mock shape mirrors the ``.values_list("id", "codings__code",
    "codings__system")`` rows the refactored helper iterates over.
    """
    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    rows = [
        ("cond-a", "I10", "http://hl7.org/fhir/sid/icd-10-cm"),
        ("cond-b", "E11.9", "http://hl7.org/fhir/sid/icd-10-cm"),
    ]
    with _patch_active_conditions_values_list(rows):
        index = _build_active_condition_icd10_index(note)
    assert index == {"I10": "cond-a", "E119": "cond-b"}


def test_build_active_condition_icd10_index_skips_non_icd_systems() -> None:
    """Codings whose ``system`` doesn't look like ICD-10 are ignored.

    Without this filter, SNOMED/UMLS codings could collide with ICD-10
    keys (different code spaces) and stamp the wrong condition_id.
    """
    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    rows = [
        # Same condition has both a SNOMED coding (skipped) and an ICD-10
        # coding (kept). The .values_list LEFT JOIN naturally yields one
        # row per (condition, coding) pair.
        ("cond-a", "12345", "http://snomed.info/sct"),
        ("cond-a", "I10", "http://hl7.org/fhir/sid/icd-10-cm"),
    ]
    with _patch_active_conditions_values_list(rows):
        index = _build_active_condition_icd10_index(note)
    assert index == {"I10": "cond-a"}


def test_build_active_condition_icd10_index_skips_null_coding_rows() -> None:
    """A condition with no codings produces a row with NULL code/system
    under the LEFT JOIN in ``.values_list("id", "codings__code", "codings__system")``.
    The helper must skip those rows (the ``if not coding_code`` guard).

    Without this pin, a follow-up refactor could regress by attempting to
    normalize an empty string and stamping a bogus key.
    """
    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    rows = [
        ("cond-orphan", None, None),  # condition without any codings
        ("cond-a", "I10", "http://hl7.org/fhir/sid/icd-10-cm"),
    ]
    with _patch_active_conditions_values_list(rows):
        index = _build_active_condition_icd10_index(note)
    assert index == {"I10": "cond-a"}


def test_build_active_condition_icd10_index_coerces_uuid_to_str() -> None:
    """KOALA-5635 round-2: ``.values_list`` on Postgres returns ``uuid.UUID``
    for UUIDField columns (not str). The downstream carry-forward filter
    ``Assessment.objects.filter(condition__id=...)`` compares against the
    SDK string convention, so the helper must coerce.

    Pin the coercion explicitly — a regression here would silently break
    integration with carry_forward_assess_background.
    """
    import uuid as _uuid

    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    raw_uuid = _uuid.UUID("12345678-1234-5678-1234-567812345678")
    rows = [(raw_uuid, "I10", "http://hl7.org/fhir/sid/icd-10-cm")]
    with _patch_active_conditions_values_list(rows):
        index = _build_active_condition_icd10_index(note)
    assert index == {"I10": str(raw_uuid)}
    # Belt-and-suspenders: the value MUST be a str, not a UUID instance.
    assert isinstance(index["I10"], str)


def test_build_active_condition_icd10_index_no_patient_returns_empty() -> None:
    """Defensive: a note without a patient must not raise."""
    note = MagicMock()
    note.patient = None
    note.id = "note-uuid-1"
    assert _build_active_condition_icd10_index(note) == {}


def test_build_active_condition_icd10_index_swallows_orm_errors() -> None:
    """Carry-forward is best-effort: ORM exceptions must NOT propagate.

    A transient DB blip during /generate-summary mustn't kill the request;
    stamping is purely additive convenience. Round-2: broad ``except
    Exception:`` is retained at THIS site because the failure mode is
    transient ORM error during a queryset chain (vs malformed input,
    which the two ``note_uuid`` sites now pre-validate with ``uuid.UUID``).
    """
    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    chain = MagicMock()
    chain.active.return_value = chain
    chain.for_patient.return_value = chain
    chain.values_list.side_effect = RuntimeError("transient db error")
    with patch("canvas_sdk.v1.data.condition.Condition.objects", chain):
        index = _build_active_condition_icd10_index(note)
    assert index == {}


def test_split_plan_stamps_condition_id_when_icd_matches_active_condition() -> None:
    """KOALA-5635: split_plan_into_diagnoses stamps ``data.condition_id``
    on diagnose proposals whose ``icd10_code`` matches an active condition
    on the note's patient.

    This is what makes the per-(patient, condition) background carry-forward
    eligible for rec-diagnose proposals — without ``condition_id``, the
    carry_forward_assess_background helper short-circuits.
    """
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Hypertension\n- Continue lisinopril"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Hypertension", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
        ],
    }
    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    rows = [("cond-htn", "I10", "http://hl7.org/fhir/sid/icd-10-cm")]
    with _patch_active_conditions_values_list(rows):
        updated, _ = split_plan_into_diagnoses(commands, section_conditions, note=note)
    assert len(updated) == 1
    assert updated[0]["command_type"] == "diagnose"
    assert updated[0]["data"]["icd10_code"] == "I10"
    assert updated[0]["data"]["condition_id"] == "cond-htn"


def test_split_plan_stamps_condition_id_normalizes_dots_and_case() -> None:
    """The active-condition index lookup uses the same normalization as the
    frontend handleInsert match step (strip dots, uppercase). A proposal
    with ``icd10_code="e11.9"`` must match an active condition coded
    ``E119`` and vice-versa.
    """
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Type 2 diabetes\n- Continue metformin"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Type 2 diabetes", "coding": [{"code": "E11.9", "display": "Type 2 diabetes"}]},
        ],
    }
    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    # Active condition stored WITHOUT the dot to prove the normalization.
    rows = [("cond-dm2", "E119", "http://hl7.org/fhir/sid/icd-10-cm")]
    with _patch_active_conditions_values_list(rows):
        updated, _ = split_plan_into_diagnoses(commands, section_conditions, note=note)
    assert updated[0]["data"]["condition_id"] == "cond-dm2"


def test_split_plan_no_stamp_when_icd_does_not_match_active_condition() -> None:
    """Diagnose proposals whose ICD does NOT match any active condition stay
    unstamped — they remain plain diagnose rows, no carry-forward eligibility,
    no Background field in the UI."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Migraine\n- Start sumatriptan"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Migraine", "coding": [{"code": "G43.909", "display": "Migraine"}]},
        ],
    }
    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    # Patient has a condition, but a different ICD than the diagnose.
    rows = [("cond-htn", "I10", "http://hl7.org/fhir/sid/icd-10-cm")]
    with _patch_active_conditions_values_list(rows):
        updated, _ = split_plan_into_diagnoses(commands, section_conditions, note=note)
    assert updated[0]["command_type"] == "diagnose"
    assert "condition_id" not in updated[0]["data"]


def test_split_plan_no_stamp_when_note_is_none() -> None:
    """Backward compatibility: callers that don't pass ``note`` get the
    pre-KOALA-5635 behavior (no stamping). The single new wiring site is
    ``post_generate_summary``; other tests / call sites that build the
    diagnose list without DB context must keep working as-is."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Hypertension\n- Continue lisinopril"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Hypertension", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
        ],
    }
    updated, _ = split_plan_into_diagnoses(commands, section_conditions)
    assert updated[0]["command_type"] == "diagnose"
    assert "condition_id" not in updated[0]["data"]


def test_split_plan_no_stamp_when_icd_code_absent() -> None:
    """When the diagnose proposal has no ICD code (no match in Nabla's
    section_conditions), the active-condition lookup is irrelevant —
    nothing to match against. Proposal stays unstamped."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Some unmatched header\n- Monitor"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions: dict[str, list[dict[str, Any]]] = {"assessment_and_plan": []}
    note = MagicMock()
    note.patient.id = "patient-key-1"
    note.id = "note-uuid-1"
    rows = [("cond-htn", "I10", "http://hl7.org/fhir/sid/icd-10-cm")]
    with _patch_active_conditions_values_list(rows):
        updated, _ = split_plan_into_diagnoses(commands, section_conditions, note=note)
    assert updated[0]["command_type"] == "diagnose"
    assert updated[0]["data"]["icd10_code"] is None
    assert "condition_id" not in updated[0]["data"]
