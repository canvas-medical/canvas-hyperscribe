from __future__ import annotations

import re
from typing import Any, TYPE_CHECKING

from canvas_sdk.v1.data.condition import Condition as ConditionModel
from logger import log

if TYPE_CHECKING:
    from canvas_sdk.v1.data.note import Note

    # Annotation-only imports (``from __future__ import annotations`` keeps these
    # as strings at runtime, so there is no import cycle even though
    # ``diagnosis_candidates`` imports text helpers from this module).
    from hyperscribe.scribe.commands.diagnosis_candidates import (
        PatientConditionSnapshot,
        ScienceSearch,
    )


_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "of",
        "and",
        "or",
        "with",
        "without",
        "in",
        "on",
        "for",
        "to",
        "by",
        "is",
        "are",
        "was",
        "were",
        "not",
        "no",
        "possible",
        "probable",
        "likely",
        "suspected",
        "unspecified",
        "specified",
        "other",
        "disorder",
        "disease",
        "syndrome",
        "condition",
        "type",
        "acute",
        "chronic",
        "primary",
        "secondary",
    }
)

_PLAN_SECTION_KEYS = frozenset({"assessment_and_plan", "plan"})


class APBlock:
    def __init__(self, header: str, body: list[str] | None = None) -> None:
        self.header = header
        self.body: list[str] = body if body is not None else []


def parse_ap_blocks(text: str) -> list[APBlock]:
    """Split A&P narrative text into header+body blocks.

    Mirrors the JavaScript ``parseAPBlocks`` in soap-group.js.
    """
    if not text:
        return []
    lines = text.split("\n")
    blocks: list[APBlock] = []
    current: APBlock | None = None

    for line in lines:
        trimmed = line.strip()
        if trimmed == "":
            if current is not None:
                blocks.append(current)
                current = None
            continue
        is_bullet = bool(re.match(r"^[-•*]", trimmed))
        if not is_bullet and current is None:
            current = APBlock(header=trimmed)
        elif not is_bullet and current is not None and len(current.body) == 0:
            current.header = current.header + "\n" + trimmed
        elif current is not None:
            current.body.append(trimmed)
        else:
            current = APBlock(header="", body=[trimmed])

    if current is not None:
        blocks.append(current)
    return blocks


def significant_words(text: str) -> list[str]:
    """Extract meaningful words, filtering stop words."""
    cleaned = re.sub(r"[^a-z0-9\s]", "", text.lower())
    return [w for w in cleaned.split() if len(w) > 1 and w not in _STOP_WORDS]


def word_overlap(a: str, b: str) -> float:
    """Calculate word-overlap similarity between two strings."""
    set_a = set(significant_words(a))
    words_b = significant_words(b)
    if not set_a or not words_b:
        return 0.0
    matches = sum(1 for w in words_b if w in set_a)
    return matches / min(len(set_a), len(words_b))


def match_condition(header: str, conditions: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Fuzzy-match a block header to a condition from normalized data.

    Two-pass algorithm matching the JavaScript ``matchCondition`` in soap-group.js:
    1. Exact substring match (case-insensitive) in either direction.
    2. Significant-word overlap >= 50%.
    """
    if not conditions or not header:
        return None
    norm = header.lower()

    # Pass 1: exact substring.
    for c in conditions:
        display = (c.get("display") or "").lower()
        if display and (norm in display or display in norm):
            return c
        for code in c.get("coding") or []:
            cd = (code.get("display") or "").lower()
            if cd and (norm in cd or cd in norm):
                return c

    # Pass 2: word overlap.
    best: dict[str, Any] | None = None
    best_score = 0.0
    for c in conditions:
        display = c.get("display") or ""
        scores = [word_overlap(header, display)]
        for code in c.get("coding") or []:
            scores.append(word_overlap(header, code.get("display") or ""))
        score = max(scores)
        if score > best_score:
            best_score = score
            best = c

    return best if best_score >= 0.5 else None


def _serialize_proposal(
    command_type: str,
    display: str,
    data: dict[str, Any],
    section_key: str,
) -> dict[str, Any]:
    return {
        "command_type": command_type,
        "display": display,
        "data": data,
        "selected": True,
        "section_key": section_key,
        "already_documented": False,
    }


def _normalize_icd10(code: str | None) -> str:
    """Normalize an ICD-10 code for equality compare.

    Mirrors the frontend ``handleInsert`` diagnose→assess flip in summary.js:
    strip dots and uppercase. Centralizes the convention so backend and
    frontend can't drift on what "same code" means.
    """
    if not code:
        return ""
    return code.replace(".", "").upper()


def _build_active_condition_icd10_index(note: Note) -> dict[str, str]:
    """Map normalized ICD-10 code → SDK condition_id for the note's patient.

    Returns ``{}`` when the note has no patient, the lookup raises, or no
    active conditions are found. The carry-forward / stamping is best-effort:
    a missing match just means the diagnose proposal stays an unattached
    ``diagnose`` (the frontend ``handleInsert`` patient-condition match step
    is the existing safety net at insert time).

    Uses ``ConditionModel.objects.active().for_patient(patient_id)`` to
    mirror ``/patient-conditions``. The SDK ``condition.id`` corresponds to
    home-app ``externally_exposable_id`` — the same shape the
    ``carry_forward_assess_background`` helper expects in
    ``proposal_data["condition_id"]`` (it filters ``condition__id=...``).
    """
    patient = getattr(note, "patient", None)
    if patient is None:
        return {}
    patient_id = getattr(patient, "id", None)
    if not patient_id:
        return {}
    index: dict[str, str] = {}
    try:
        # Per CLAUDE.md ("never fetch full objects from the database if you
        # only need a couple properties"): pull just (condition_id,
        # coding_code, coding_system) via ``.values_list()`` instead of
        # ``.prefetch_related("codings")`` over full ORM objects. The
        # ``codings`` reverse-FK join is expressed as a double-underscore
        # field path; Django emits a LEFT JOIN to the coding table and
        # yields one row per (condition, coding) pair. Conditions without
        # any codings still surface (with NULL code/system) but get
        # skipped by the ``not coding_code`` guard below.
        rows = (
            ConditionModel.objects.active()
            .for_patient(str(patient_id))
            .values_list("id", "codings__code", "codings__system")
        )
        for condition_id_raw, coding_code, coding_system in rows:
            if not coding_code:
                continue
            if "icd" not in (coding_system or "").lower():
                continue
            normalized = _normalize_icd10(coding_code)
            if not normalized or normalized in index:
                continue
            # Coerce condition_id to str: UUIDField on Postgres yields
            # ``uuid.UUID`` from .values_list(), but downstream callers
            # (carry_forward filter on ``condition__id=...``) compare
            # against string form per SDK ID-mapping convention.
            index[normalized] = str(condition_id_raw)
    except Exception:
        # The carry-forward/stamping is best-effort — a transient ORM error
        # MUST NOT kill /generate-summary. Broad ``Exception`` is retained
        # here (vs the narrow ``Note.DoesNotExist`` used at the two
        # ``note_uuid`` lookup sites) because the failure mode is different:
        # this catches transient DB/ORM errors during a custom-manager
        # queryset chain, not malformed user input. ``note.id`` is
        # internal-only and PHI-safe; do NOT log condition payloads,
        # patient identifiers, or any clinical content.
        log.exception(
            "active condition icd10 index lookup failed for note %s",
            getattr(note, "id", None),
        )
        return {}
    return index


def split_plan_into_diagnoses(
    commands: list[dict[str, Any]],
    section_conditions: dict[str, list[dict[str, Any]]],
    note: Note | None = None,
    *,
    chart_conditions: list[PatientConditionSnapshot] | None = None,
    science_search: ScienceSearch | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Replace the plan/assessment_and_plan command with per-condition diagnose commands.

    Returns ``(updated_commands, unmatched_conditions)`` where *unmatched_conditions*
    are conditions from normalized data that no A&P block claimed.

    Code selection is delegated to the grounded ranker in ``diagnosis_candidates``:
    for each block, ALL codings of the associated Nabla condition(s) — plus the
    patient's chart codes (``chart_conditions``) and, as a last resort, a grounded
    science search (``science_search``) — enter a clinically-ranked candidate set.
    A single confident match is auto-applied; otherwise the block is left UNCODED
    and ``data["candidate_suggestions"]`` carries the ranked options for the
    provider to pick. This replaces the old first-match-wins ``next(...)`` pick,
    which let an incidental symptom code (e.g. R45.851) win over the real
    diagnosis (e.g. F33.1) and orphaned the rest.

    Each proposal is stamped with a stable ``data["block_id"]`` (``apblock-{i}``),
    the association key used downstream instead of the mutable condition header.

    KOALA_5635_STAMP_CONDITION_ID — a proposal whose chosen code matches an ACTIVE
    condition on the patient gets ``data["condition_id"]`` stamped (from the
    ``note``-derived active index and/or the chosen chart candidate), keeping it
    eligible for the diagnose→assess flip. Resolved/inactive matches never carry a
    condition_id (the SDK has no reactivation command).

    Why the keyword args are optional: the pure (no DB / no network) contract is
    preserved for existing callers — when ``chart_conditions``/``science_search``
    are omitted, ranking runs on the Nabla codings alone (which already fixes the
    symptom-over-diagnosis defect).
    """
    ap_idx = -1
    for i, c in enumerate(commands):
        if c.get("command_type") == "plan" and c.get("section_key") in _PLAN_SECTION_KEYS:
            ap_idx = i
            break

    if ap_idx == -1:
        return commands, []

    ap_cmd = commands[ap_idx]
    codes = section_conditions.get("assessment_and_plan") or section_conditions.get("plan") or []
    blocks = parse_ap_blocks(ap_cmd.get("data", {}).get("narrative", ""))
    if not blocks:
        return commands, []

    # Lazy import to avoid an import cycle: ``diagnosis_candidates`` imports the
    # text helpers (``word_overlap`` / ``significant_words``) from this module at
    # load time, so this module must not import it at module scope.
    from hyperscribe.scribe.commands.diagnosis_candidates import (
        build_block_candidates,
        expand_unspecified,
        is_unspecified_code,
        serialize_candidate,
        surface_candidates,
    )

    diagnose_commands: list[dict[str, Any]] = []
    claimed: set[int] = set()
    # KOALA_5635_STAMP_CONDITION_ID — build the active-condition ICD-10 index
    # once per call (not per block) so we don't N+1 patient_conditions per
    # diagnose proposal. ``{}`` when ``note`` is None or the lookup fails.
    active_icd10_index = _build_active_condition_icd10_index(note) if note is not None else {}
    chart = chart_conditions or []

    for i, block in enumerate(blocks):
        block_id = f"apblock-{i}"
        # Strip a trailing colon from the header. split_by_problem templates emit
        # problem headers as "Diagnosis:" (followed by bulleted plan), and the
        # colon breaks the exact match against Nabla's colon-less
        # corresponding_note_problem (e.g. header "Right rotator cuff tendinitis:"
        # vs problem "Right rotator cuff tendinitis" → missed M75.41). Normalize
        # once and use it for matching, display, and the stored condition_header.
        header = block.header.strip()
        if header.endswith(":"):
            header = header[:-1].strip()

        # Associate Nabla condition(s) with this block. Exact
        # ``corresponding_note_problem`` matches first — note there may be SEVERAL
        # (Nabla attaches the same note problem to a definitive code AND incidental
        # symptom codes), and we keep ALL of them so the ranker, not list order,
        # decides. Falls back to a single fuzzy header match.
        nabla_for_block = [
            c
            for c in codes
            if c.get("corresponding_note_problem") and c["corresponding_note_problem"].strip().lower() == header.lower()
        ]
        if not nabla_for_block:
            fuzzy = match_condition(header, codes)
            if fuzzy is not None:
                nabla_for_block = [fuzzy]
        for condition in nabla_for_block:
            claimed.add(id(condition))

        # Full note text for this block (header + assessment). Used to (a) let the
        # science fallback recover a code via a body synonym the header lacks, and
        # (b) rank unspecified refinements by documented specificity.
        context_text = f"{header}\n" + "\n".join(block.body)
        block_candidates = build_block_candidates(
            block_id, header, nabla_for_block, chart, science_search, context_text=context_text
        )
        chosen = block_candidates.chosen

        # An unspecified code is NOT auto-applied when grounded more-specific options
        # exist: the block is left UNCODED and the picker offers the unspecified code
        # FIRST, then the more-specific siblings — so the provider picks (one click to
        # keep the unspecified, or refine). When no more-specific option exists there's
        # nothing to choose between, so the unspecified code is applied as-is (avoids a
        # pointless one-option picker).
        unspecified_options: list = []
        if chosen is not None and is_unspecified_code(chosen.code, chosen.display):
            # Rank both the unspecified code and its refinements by how well each matches
            # the documented note text, so a specificity the note actually states (e.g.
            # "moderate" -> F32.1) leads and the unspecified only leads when it's vague.
            children = expand_unspecified(chosen, science_search, context_text=context_text)
            if children:
                unspecified_options = sorted(
                    [chosen, *children],
                    key=lambda candidate: word_overlap(context_text, candidate.display),
                    reverse=True,
                )
                chosen = None  # defer to a provider pick

        data: dict[str, Any] = {
            "icd10_code": chosen.raw_code if chosen else None,
            "icd10_display": chosen.display if chosen else "",
            "condition_header": header,
            "today_assessment": "\n".join(block.body),
            "accepted": False,
            "block_id": block_id,
        }
        display = (chosen.display if chosen else "") or header

        if chosen is not None:
            # condition_id: the ``note``-derived active index (existing path) OR the
            # chosen chart candidate's id. Both are ACTIVE-only — a resolved/inactive
            # match never carries a condition_id, so the diagnose→assess flip can't
            # attach an assessment to a resolved record (no SDK reactivation).
            stamped_id = active_icd10_index.get(_normalize_icd10(chosen.raw_code)) or chosen.condition_id
            if stamped_id:
                data["condition_id"] = stamped_id
        elif unspecified_options:
            # Uncoded: keep-as-unspecified (first) or refine to a more-specific code.
            data["candidate_suggestions"] = [serialize_candidate(c) for c in surface_candidates(unspecified_options)]
        elif block_candidates.ambiguous:
            # Leave the card UNCODED and surface the ranked options (with provenance) for
            # the provider to choose. surface_candidates drops incidental symptom/context
            # codes (e.g. R45.851 "Suicidal ideations" under a depression problem) when a
            # definitive option exists, and caps the list. Never auto-stamp.
            data["candidate_suggestions"] = [
                serialize_candidate(c) for c in surface_candidates(block_candidates.candidates)
            ]

        diagnose_commands.append(
            _serialize_proposal(
                command_type="diagnose",
                display=display,
                data=data,
                section_key=ap_cmd.get("section_key", "assessment_and_plan"),
            )
        )

    unmatched = [c for c in codes if id(c) not in claimed]
    updated = [*commands[:ap_idx], *diagnose_commands, *commands[ap_idx + 1 :]]
    return updated, unmatched
