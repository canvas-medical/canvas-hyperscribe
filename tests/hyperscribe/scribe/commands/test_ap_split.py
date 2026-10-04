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
from hyperscribe.scribe.commands.diagnosis_candidates import PatientConditionSnapshot
from hyperscribe.structures.icd10_condition import Icd10Condition


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
    # Never auto-applied: every diagnose is uncoded; the code is surfaced as the top pick.
    assert updated[1]["command_type"] == "diagnose"
    assert updated[1]["data"]["icd10_code"] is None
    assert updated[1]["data"]["accepted"] is False
    assert updated[1]["data"]["candidate_suggestions"][0]["formatted_code"] == "G43.909"
    assert updated[2]["command_type"] == "diagnose"
    assert updated[2]["data"]["icd10_code"] is None
    assert updated[2]["data"]["candidate_suggestions"][0]["formatted_code"] == "I10"
    assert unmatched == []
    # today_assessment leads with the original A&P headline (persisted for reference,
    # inside the editable text), then the block body.
    assert updated[1]["data"]["today_assessment"] == "Migraine\n- Start sumatriptan"
    assert updated[2]["data"]["today_assessment"] == "Hypertension\n- Continue lisinopril"


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
    assert updated[0]["data"]["icd10_code"] is None
    assert updated[0]["data"]["accepted"] is False
    assert updated[0]["data"]["candidate_suggestions"][0]["formatted_code"] == "J06.9"


def test_split_plan_strips_trailing_colon_from_split_by_problem_header() -> None:
    """split_by_problem headers arrive as 'Diagnosis:' — the trailing colon must be
    stripped so the exact corresponding_note_problem match still lands (regression:
    'Right rotator cuff tendinitis:' previously missed M75.41)."""
    commands = [
        {
            "command_type": "plan",
            "data": {
                "narrative": (
                    "Right rotator cuff tendinitis:\n"
                    "- Consistent with rotator cuff tendinitis or impingement.\n"
                    "- Referred to orthopedics."
                )
            },
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "",
                "coding": [{"code": "M75.41", "display": "Impingement syndrome of right shoulder"}],
                "corresponding_note_problem": "Right rotator cuff tendinitis",
            },
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    assert updated[0]["data"]["icd10_code"] is None
    assert updated[0]["data"]["candidate_suggestions"][0]["formatted_code"] == "M75.41"
    # The stored header is colon-stripped, not "Right rotator cuff tendinitis:".
    assert updated[0]["data"]["condition_header"] == "Right rotator cuff tendinitis"
    assert unmatched == []


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
    # Diarrhea surfaces R19.7, NOT D86.9
    assert updated[0]["data"]["icd10_code"] is None
    assert updated[0]["data"]["candidate_suggestions"][0]["formatted_code"] == "R19.7"
    # Sarcoidosis surfaces D86.9
    assert updated[1]["data"]["icd10_code"] is None
    assert updated[1]["data"]["candidate_suggestions"][0]["formatted_code"] == "D86.9"


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
    assert updated[0]["data"]["icd10_code"] is None
    assert updated[0]["data"]["candidate_suggestions"][0]["formatted_code"] == "J06.9"


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
    assert updated[0]["data"]["icd10_code"] is None
    assert updated[0]["data"]["candidate_suggestions"][0]["formatted_code"] == "R51.9"


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


def test_split_plan_never_stamps_condition_id() -> None:
    """Codes are never auto-applied, so the belt never stamps ``condition_id`` — even when
    the diagnosis matches an active condition on the note's patient. The code is surfaced
    as the top picker option instead; the diagnose→assess flip now happens at insert time
    when the provider-picked code matches the active problem list (summary.js).
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
    assert updated[0]["data"]["icd10_code"] is None
    assert "condition_id" not in updated[0]["data"]
    assert updated[0]["data"]["candidate_suggestions"][0]["formatted_code"] == "I10"


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


# --- ICD-10 ranker integration (P2) ---


def test_split_plan_stamps_stable_block_id() -> None:
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Migraine\n- Sumatriptan\n\nHypertension\n- Lisinopril"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {"display": "Migraine", "coding": [{"code": "G43.909", "display": "Migraine, unspecified"}]},
            {"display": "Hypertension", "coding": [{"code": "I10", "display": "Essential hypertension"}]},
        ],
    }
    updated, _ = split_plan_into_diagnoses(commands, section_conditions)
    assert updated[0]["data"]["block_id"] == "apblock-0"
    assert updated[1]["data"]["block_id"] == "apblock-1"


def test_split_plan_ranks_definitive_over_incidental_symptom() -> None:
    """The Jodie Foster regression in the belt's real shape: Nabla returns TWO
    conditions for one A&P problem (same corresponding_note_problem) — a symptom
    code listed first and the definitive code second. The ranker must pick the
    definitive code and orphan nothing."""
    header = "Major depressive disorder, recurrent, moderate to severe"
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": f"{header}\n- Increase sertraline"},
            "section_key": "assessment_and_plan",
        },
    ]
    suicidal = {
        "display": "Suicidal ideations",
        "coding": [{"code": "R45.851", "display": "Suicidal ideations"}],
        "corresponding_note_problem": header,
    }
    depression = {
        "display": "Major depressive disorder, recurrent, moderate",
        "coding": [{"code": "F33.1", "display": "Major depressive disorder, recurrent, moderate"}],
        "corresponding_note_problem": header,
    }
    section_conditions = {"assessment_and_plan": [suicidal, depression]}
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert len(updated) == 1
    # Never auto-applied: uncoded, definitive F33.1 leads the picker, symptom code dropped.
    assert updated[0]["data"]["icd10_code"] is None
    codes = [s["formatted_code"] for s in updated[0]["data"]["candidate_suggestions"]]
    assert codes[0] == "F33.1"  # definitive leads over the incidental symptom code
    assert "R45.851" not in codes
    # No orphaning: both conditions were claimed by the block.
    assert unmatched == []


def test_split_plan_ambiguous_block_left_uncoded_with_suggestions() -> None:
    header = "Headache"
    commands = [
        {"command_type": "plan", "data": {"narrative": f"{header}\n- Imaging"}, "section_key": "assessment_and_plan"},
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Vascular headache",
                "coding": [{"code": "G44.1", "display": "Vascular headache, not elsewhere classified"}],
                "corresponding_note_problem": header,
            },
            {
                "display": "Tension-type headache",
                "coding": [{"code": "G44.209", "display": "Tension-type headache, unspecified"}],
                "corresponding_note_problem": header,
            },
        ],
    }
    updated, unmatched = split_plan_into_diagnoses(commands, section_conditions)
    assert updated[0]["data"]["icd10_code"] is None
    suggestions = updated[0]["data"]["candidate_suggestions"]
    codes = {s["code"] for s in suggestions}
    assert {"G44.1", "G44.209"} <= codes
    assert all(s["provenance"] == "Detected in note" for s in suggestions)
    assert unmatched == []


def test_split_plan_prefers_charted_specific_over_nabla_unspecified() -> None:
    """A more-specific code on the patient's chart beats Nabla's unspecified code in the
    ranked picker (it leads). Never auto-applied — the provider picks; the assess flip
    happens at insert when the picked code matches the active problem."""
    header = "Type 2 diabetes mellitus"
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": f"{header}\n- Continue metformin"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Type 2 diabetes mellitus without complications",
                "coding": [{"code": "E11.9", "display": "Type 2 diabetes mellitus without complications"}],
                "corresponding_note_problem": header,
            },
        ],
    }
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
    updated, _ = split_plan_into_diagnoses(commands, section_conditions, chart_conditions=chart)
    assert updated[0]["data"]["icd10_code"] is None
    assert "condition_id" not in updated[0]["data"]  # never auto-applied → no flip-stamp
    codes = [s["formatted_code"] for s in updated[0]["data"]["candidate_suggestions"]]
    assert codes[0] == "E11.65"  # charted specific leads over Nabla's E11.9


def test_split_plan_surfaces_cross_family_chart_note_conflict() -> None:
    """UAT regression: a stale active problem F32.1 (single episode) must not override
    the encounter-documented F33.1 (recurrent). The card is left uncoded with both
    options surfaced (chart + note provenance) for the provider to choose."""
    header = "Major depressive disorder, recurrent, moderate to severe"
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": f"{header}\n- Increase sertraline"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Major depressive disorder, recurrent, moderate",
                "coding": [{"code": "F33.1", "display": "Major depressive disorder, recurrent, moderate"}],
                "corresponding_note_problem": header,
            },
            # Nabla also attached an incidental symptom code to the same problem.
            {
                "display": "Suicidal ideations",
                "coding": [{"code": "R45.851", "display": "Suicidal ideations"}],
                "corresponding_note_problem": header,
            },
        ],
    }
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
    updated, _ = split_plan_into_diagnoses(commands, section_conditions, chart_conditions=chart)
    data = updated[0]["data"]
    assert data["icd10_code"] is None
    codes = {s["formatted_code"] for s in data["candidate_suggestions"]}
    assert {"F32.1", "F33.1"} <= codes
    # The incidental "Suicidal ideations" symptom code is NOT offered as a choice.
    assert "R45.851" not in codes
    provs = {s["provenance"] for s in data["candidate_suggestions"]}
    assert "Active problem" in provs
    assert "Detected in note" in provs


def test_split_plan_unspecified_with_refinements_left_uncoded() -> None:
    """An unspecified code is NOT auto-applied when more-specific options exist: the
    block is left uncoded and the picker offers the unspecified code first, then the
    refinements (no `unspecified` flag, no auto-stamp)."""
    commands = [
        {"command_type": "plan", "data": {"narrative": "Insomnia\n- Trazodone"}, "section_key": "assessment_and_plan"},
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Insomnia, unspecified",
                "coding": [{"code": "G47.00", "display": "Insomnia, unspecified"}],
                "corresponding_note_problem": "Insomnia",
            },
        ],
    }

    def science(_expressions: list[str]) -> list[Icd10Condition]:
        return [
            Icd10Condition(code="G4700", label="Insomnia, unspecified"),
            Icd10Condition(code="G4701", label="Insomnia due to medical condition"),
            Icd10Condition(code="G4709", label="Other insomnia"),
        ]

    updated, _ = split_plan_into_diagnoses(commands, section_conditions, science_search=science)
    data = updated[0]["data"]
    assert data["icd10_code"] is None
    assert "unspecified" not in data
    formatted = [s["formatted_code"] for s in data["candidate_suggestions"]]
    assert formatted[0] == "G47.00"  # unspecified offered first
    assert "G47.01" in formatted and "G47.09" in formatted
    assert data["candidate_suggestions"][0]["provenance"] == "Detected in note"
    assert data["candidate_suggestions"][1]["provenance"] == "More specific option"


def test_split_plan_unspecified_ranks_documented_specificity_first() -> None:
    """Option B: when the note documents a specificity (e.g. 'moderate'), the matching
    specific code leads the picker over the unspecified code Nabla emitted."""
    header = "Major depressive disorder"
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": f"{header}\n- Moderate depression, PHQ-9 12. Start therapy."},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Major depressive disorder, single episode, unspecified",
                "coding": [{"code": "F32.9", "display": "Major depressive disorder, single episode, unspecified"}],
                "corresponding_note_problem": header,
            },
        ],
    }

    def science(_expressions: list[str]) -> list[Icd10Condition]:
        return [
            Icd10Condition(code="F329", label="Major depressive disorder, single episode, unspecified"),
            Icd10Condition(code="F320", label="Major depressive disorder, single episode, mild"),
            Icd10Condition(code="F321", label="Major depressive disorder, single episode, moderate"),
            Icd10Condition(code="F322", label="Major depressive disorder, single episode, severe"),
        ]

    updated, _ = split_plan_into_diagnoses(commands, section_conditions, science_search=science)
    data = updated[0]["data"]
    assert data["icd10_code"] is None
    formatted = [s["formatted_code"] for s in data["candidate_suggestions"]]
    assert formatted[0] == "F32.1"  # documented "moderate" leads
    assert "F32.9" in formatted  # the unspecified is still offered, just not first


def test_split_plan_science_fallback_uses_body_synonym() -> None:
    """When Nabla emits no code for a block, the science fallback searches the
    assessment body too, so a synonym there (impingement) recovers M75.4x that the
    header ('tendinitis') alone would miss."""
    header = "Right rotator cuff tendinitis"
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": f"{header}\n- Consistent with rotator cuff tendinitis or impingement. Refer ortho."},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions: dict[str, list[dict[str, Any]]] = {"assessment_and_plan": []}

    def science(expressions: list[str]) -> list[Icd10Condition]:
        if any("impingement" in expression for expression in expressions):
            return [Icd10Condition(code="M7541", label="Impingement syndrome of right shoulder")]
        return []

    updated, _ = split_plan_into_diagnoses(commands, section_conditions, science_search=science)
    data = updated[0]["data"]
    assert data["icd10_code"] is None
    assert "M75.41" in [s["formatted_code"] for s in data["candidate_suggestions"]]


def test_split_plan_unspecified_without_refinements_surfaced() -> None:
    """When no more-specific option exists, the unspecified code is surfaced as the single
    picker option (never auto-applied)."""
    commands = [
        {
            "command_type": "plan",
            "data": {"narrative": "Hypothyroidism\n- Continue levothyroxine"},
            "section_key": "assessment_and_plan",
        },
    ]
    section_conditions = {
        "assessment_and_plan": [
            {
                "display": "Hypothyroidism, unspecified",
                "coding": [{"code": "E03.9", "display": "Hypothyroidism, unspecified"}],
                "corresponding_note_problem": "Hypothyroidism",
            },
        ],
    }
    updated, _ = split_plan_into_diagnoses(commands, section_conditions, science_search=lambda _e: [])
    data = updated[0]["data"]
    assert data["icd10_code"] is None
    assert data["candidate_suggestions"][0]["formatted_code"] == "E03.9"
