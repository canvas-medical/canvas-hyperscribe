"""Grounded, ranked ICD-10 candidate selection for A&P diagnosis blocks.

This module replaces the old "first-match-wins" code pick in
``split_plan_into_diagnoses`` (``ap_split.py``) with a retrieval-grounded,
clinically-ranked candidate model. It NEVER invents a code: every candidate is
sourced from the patient's chart (active or inactive conditions), Nabla's
normalized codings for the block, or a grounded science-service search. The LLM
is not involved here.

Why this exists (see KOALA / the ICD-10 redesign plan): Nabla frequently returns
several codings for a single A&P problem — a definitive diagnosis plus incidental
symptom/sign codes pulled from the plan narrative (e.g. for a depression block it
emits both ``F33.1`` *and* ``R45.851`` "Suicidal ideations"). The old belt took
whichever appeared first and discarded the rest, so a Chapter-18 symptom code
could silently replace the real diagnosis. Here, all codings enter a ranked set
and clinical priority decides — with the patient's own chart code preferred over
Nabla's (Nabla skews toward unspecified), and symptom/context codes deprioritized
when a definitive code is available.

Purity / sandbox notes: all containers are ``typing.NamedTuple`` (the plugin
sandbox can't evaluate ``@dataclass`` at module-load — see ``problem_list_match``).
The module has no DB or network imports; ``science_search`` is injected by the
caller (defaulting to ``CanvasScience.search_conditions`` at the call site), which
keeps the engine pure and trivially unit-testable.
"""

from __future__ import annotations

from typing import Any, Callable, NamedTuple

# Reused text/code helpers. These imports are one-directional: ``ap_split`` and
# ``problem_list_match`` do NOT import this module at module-load time
# (``ap_split`` imports it lazily inside ``split_plan_into_diagnoses``), so there
# is no import cycle.
from hyperscribe.scribe.commands.ap_split import significant_words, word_overlap
from hyperscribe.scribe.commands.problem_list_match import (
    _icd10_family_root,
    icd10_normalize,
)

# A callable that takes a list of search expressions and returns objects exposing
# ``.code`` and ``.label`` (e.g. ``CanvasScience.search_conditions`` →
# ``list[Icd10Condition]``). Injected so the engine stays pure.
ScienceSearch = Callable[[list[str]], list[Any]]


class CandidateSource:
    """Provenance buckets for a diagnosis candidate, ordered by trust.

    ``ACTIVE_PROBLEM`` (the patient's active problem list) is the most
    authoritative, then ``PRIOR_CONDITION`` (the patient's resolved/inactive
    history), then ``NABLA`` (codings the scribe detected for this block), then
    ``SCIENCE_SEARCH`` (a grounded ontology lookup used only as a fallback).
    ``MORE_SPECIFIC`` is not a primary source — it tags the more-specific
    children surfaced when an unspecified code is auto-applied.
    """

    ACTIVE_PROBLEM = "active_problem"
    PRIOR_CONDITION = "prior_condition"
    NABLA = "nabla"
    SCIENCE_SEARCH = "science_search"
    MORE_SPECIFIC = "more_specific"


# Trust ranking used for de-duplication (higher wins when two sources carry the
# same normalized code).
_SOURCE_TRUST = {
    CandidateSource.ACTIVE_PROBLEM: 3,
    CandidateSource.PRIOR_CONDITION: 2,
    CandidateSource.NABLA: 1,
    CandidateSource.SCIENCE_SEARCH: 0,
    CandidateSource.MORE_SPECIFIC: 0,
}


class DiagnosisCandidate(NamedTuple):
    """One ranked ICD-10 candidate for an A&P block.

    :param code: normalized dotless canonical code (``F331``) — the comparison key.
    :param raw_code: code as sourced (dotted or not); preserved for display/storage.
    :param display: human-readable label for the code.
    :param source: one of ``CandidateSource.*``.
    :param condition_id: SDK condition id — populated ONLY for ``ACTIVE_PROBLEM``
        candidates, so a confident match can flip diagnose→assess against the live
        problem-list entry. Never set for ``PRIOR_CONDITION``: the SDK has no
        reactivation command, so a recurrence must be a fresh ``Diagnose``.
    :param clinical_status: chart clinical status (active/resolved/...); "" otherwise.
    :param onset_date / resolution_date: ISO strings for provenance; "" when unknown.
    :param nabla_order: original index within Nabla's coding list (final tiebreak).
    """

    code: str
    raw_code: str
    display: str
    source: str
    condition_id: str = ""
    clinical_status: str = ""
    onset_date: str = ""
    resolution_date: str = ""
    nabla_order: int = 999


class PatientConditionSnapshot(NamedTuple):
    """A patient chart condition narrowed to what candidate assembly needs."""

    condition_id: str
    code: str
    display: str
    system: str
    clinical_status: str
    onset_date: str
    resolution_date: str


class BlockCandidates(NamedTuple):
    """The ranked outcome for a single A&P block.

    ``chosen`` is set only when one candidate is confident enough to auto-apply;
    otherwise ``ambiguous`` is True and the caller surfaces ``candidates`` (top N)
    for the provider to pick from. Both may be falsy when there are no candidates
    at all (the block stays uncoded and the provider searches manually).
    """

    block_id: str
    header: str
    candidates: list[DiagnosisCandidate]
    chosen: DiagnosisCandidate | None
    ambiguous: bool


def format_icd10(code: str) -> str:
    """Return the dotted display form of an ICD-10 code (``F331`` -> ``F33.1``)."""
    clean = (code or "").replace(".", "").upper().strip()
    return clean[:3] + "." + clean[3:] if len(clean) > 3 else clean


def is_unspecified_code(code: str, display: str = "") -> bool:
    """Return True if ``code`` is an unspecified/parent ICD-10 code.

    "Unspecified" is identified primarily from the display text (the reliable
    signal — e.g. ``G47.00`` "Insomnia, **unspecified**", whose numeric tail
    ``00`` is not otherwise distinguishable), with a numeric backstop matching the
    parent shapes used by ``icd10_is_unspecified_parent_of``: a bare 3-char root,
    a root followed by ``9``, or a root followed by ``9`` + one digit.
    """
    if display and "unspecified" in display.lower():
        return True
    norm = icd10_normalize(code)
    if not norm:
        return False
    if len(norm) == 3:
        return True
    tail = norm[3:]
    if tail == "9":
        return True
    return len(tail) == 2 and tail[0] == "9" and tail[1].isdigit()


def _is_symptom_or_context(code: str) -> bool:
    """ICD-10 Chapter 18 (``R``, symptoms/signs) or ``Z`` (contextual) code."""
    norm = icd10_normalize(code)
    return bool(norm) and norm[0] in ("R", "Z")


def provenance_label(candidate: DiagnosisCandidate) -> str:
    """Human-readable provenance shown next to a candidate in the picker."""
    source = candidate.source
    if source == CandidateSource.ACTIVE_PROBLEM:
        return "Active problem"
    if source == CandidateSource.PRIOR_CONDITION:
        # One catch-all for every non-active status (resolved / remission / relapse /
        # investigative) — the date/status variants add noise without changing what
        # the provider does (pick it to re-document).
        return "Past condition"
    if source == CandidateSource.NABLA:
        return "Detected in note"
    if source == CandidateSource.SCIENCE_SEARCH:
        return "ICD-10 search"
    if source == CandidateSource.MORE_SPECIFIC:
        return "More specific option"
    return ""


def serialize_candidate(candidate: DiagnosisCandidate) -> dict[str, str]:
    """Picker-option shape consumed by the frontend (DiagnoseRow)."""
    return {
        "code": candidate.raw_code or candidate.code,
        "formatted_code": format_icd10(candidate.code),
        "display": candidate.display,
        "provenance": provenance_label(candidate),
    }


# Cap on how many options a picker surfaces — enough to choose from, few enough to
# scan (e.g. E03 hypothyroidism has 8 family members; the provider needs a handful).
MAX_SURFACED_SUGGESTIONS = 6


def surface_candidates(candidates: list[DiagnosisCandidate]) -> list[DiagnosisCandidate]:
    """Trim a ranked candidate list for display in the picker.

    Drops symptom/context (R/Z) codes when a definitive option exists — so an
    incidental code Nabla attached to the block (e.g. R45.851 "Suicidal ideations"
    under a depression problem) is never offered as a diagnosis to pick — and caps
    the count so the list stays scannable. Order is preserved (already ranked).
    """
    has_definitive = any(not _is_symptom_or_context(candidate.code) for candidate in candidates)
    trimmed = [c for c in candidates if not (has_definitive and _is_symptom_or_context(c.code))]
    return trimmed[:MAX_SURFACED_SUGGESTIONS]


def _overlap_bucket(header: str, display: str) -> int:
    """Coarse word-overlap bucket (avoids float fragility in the sort key)."""
    overlap = word_overlap(header, display)
    if overlap >= 0.8:
        return 2
    if overlap >= 0.5:
        return 1
    return 0


def _sort_key(header: str, candidate: DiagnosisCandidate) -> tuple[int, int, int, int, int, int]:
    """Descending clinical-priority key. Tiers, most significant first:

    1. active problem-list match;
    2. prior-condition (inactive history) match;
    3. display word-overlap with the header (bucketed);
    4. definitive code over symptom/context (R/Z) — only discriminates when a
       non-R/Z candidate exists, since a uniform tier is a no-op in the sort;
    5. specificity (longer/leaf code wins);
    6. earlier Nabla order (final tiebreak).
    """
    tier_active = 1 if candidate.source == CandidateSource.ACTIVE_PROBLEM else 0
    tier_prior = 1 if candidate.source == CandidateSource.PRIOR_CONDITION else 0
    tier_overlap = _overlap_bucket(header, candidate.display)
    tier_definitive = 0 if _is_symptom_or_context(candidate.code) else 1
    tier_specificity = len(candidate.code)
    tier_nabla = -candidate.nabla_order
    return (tier_active, tier_prior, tier_overlap, tier_definitive, tier_specificity, tier_nabla)


def _dedup_by_code(candidates: list[DiagnosisCandidate]) -> list[DiagnosisCandidate]:
    """Keep one candidate per normalized code, preferring the highest-trust source."""
    by_code: dict[str, DiagnosisCandidate] = {}
    for candidate in candidates:
        existing = by_code.get(candidate.code)
        if existing is None or _SOURCE_TRUST[candidate.source] > _SOURCE_TRUST[existing.source]:
            by_code[candidate.code] = candidate
    return list(by_code.values())


def assemble_block_candidates(
    header: str,
    nabla_for_block: list[dict[str, Any]],
    chart: list[PatientConditionSnapshot],
    science_search: ScienceSearch | None = None,
) -> list[DiagnosisCandidate]:
    """Build the (de-duplicated, unranked) candidate set for one A&P block.

    :param header: the block's problem header text.
    :param nabla_for_block: the Nabla normalized-condition dicts the caller has
        already associated with this block (``{"display", "coding": [...]}``).
        EVERY coding becomes a candidate — this is the no-orphan fix.
    :param chart: the patient's condition snapshots (active and inactive).
    :param science_search: optional grounded lookup, used only as a fallback when
        there is no chart/Nabla support for the block.
    """
    candidates: list[DiagnosisCandidate] = []

    # (c) Nabla codings — emit every coding (no first-match discard).
    nabla_family_roots: set[str] = set()
    has_nabla = False
    order = 0
    for condition in nabla_for_block or []:
        condition_display = condition.get("display") or ""
        for coding in condition.get("coding") or []:
            raw = coding.get("code")
            if not raw:
                continue
            code = icd10_normalize(raw)
            if not code:
                continue
            candidates.append(
                DiagnosisCandidate(
                    code=code,
                    raw_code=raw,
                    display=coding.get("display") or condition_display or header,
                    source=CandidateSource.NABLA,
                    nabla_order=order,
                )
            )
            order += 1
            has_nabla = True
            nabla_family_roots.add(_icd10_family_root(code))

    # (a)/(b) Chart conditions that match the block (by header overlap or by
    # sharing an ICD-10 family root with a Nabla code for this block).
    has_chart_match = False
    for snapshot in chart or []:
        if not snapshot.code:
            continue
        code = icd10_normalize(snapshot.code)
        if not code:
            continue
        matches = word_overlap(header, snapshot.display) >= 0.5 or _icd10_family_root(code) in nabla_family_roots
        if not matches:
            continue
        is_active = (snapshot.clinical_status or "").lower() == "active"
        candidates.append(
            DiagnosisCandidate(
                code=code,
                raw_code=snapshot.code,
                display=snapshot.display,
                source=CandidateSource.ACTIVE_PROBLEM if is_active else CandidateSource.PRIOR_CONDITION,
                # condition_id flows ONLY for active matches (assess-flip eligibility).
                condition_id=snapshot.condition_id if is_active else "",
                clinical_status=snapshot.clinical_status,
                onset_date=snapshot.onset_date,
                resolution_date=snapshot.resolution_date,
            )
        )
        has_chart_match = True

    # (d) Science-search fallback — only when nothing grounded the block yet.
    if science_search is not None and not has_nabla and not has_chart_match:
        expression = " ".join(significant_words(header)) or header.strip()
        if expression:
            try:
                for hit in science_search([expression]) or []:
                    code = icd10_normalize(getattr(hit, "code", ""))
                    if not code:
                        continue
                    candidates.append(
                        DiagnosisCandidate(
                            code=code,
                            raw_code=getattr(hit, "code", ""),
                            display=getattr(hit, "label", ""),
                            source=CandidateSource.SCIENCE_SEARCH,
                        )
                    )
            except Exception:
                # Best-effort: a science outage must never break candidate assembly.
                pass

    return _dedup_by_code(candidates)


def rank_candidates(header: str, candidates: list[DiagnosisCandidate]) -> list[DiagnosisCandidate]:
    """Return candidates sorted best-first by clinical priority (see ``_sort_key``)."""
    return sorted(candidates, key=lambda candidate: _sort_key(header, candidate), reverse=True)


def resolve_choice(header: str, ranked: list[DiagnosisCandidate]) -> tuple[DiagnosisCandidate | None, bool]:
    """Decide whether to auto-apply the top candidate or surface a picker.

    Returns ``(chosen, ambiguous)``. ``chosen`` is non-None only when one
    candidate is confident enough to auto-apply. ``ambiguous`` is True when the
    block should stay uncoded with options surfaced. ``(None, False)`` means there
    are simply no candidates (uncoded, nothing to surface).
    """
    if not ranked:
        return None, False
    top = ranked[0]

    # A science-only candidate has no chart/Nabla support — never auto-stamp it.
    if top.source == CandidateSource.SCIENCE_SEARCH:
        return None, True

    # A symptom/context (R/Z) code at the top is auto-applied only when it strongly
    # matches the block (it IS the documented problem, e.g. R19.7 "Diarrhea,
    # unspecified" for a Diarrhea block). A weakly-matching symptom code is
    # incidental (e.g. R45.851 "Suicidal ideations" surfaced under a depression
    # header with no definitive code) — surface it for the provider, never stamp it.
    if _is_symptom_or_context(top.code) and _overlap_bucket(header, top.display) < 1:
        return None, True

    # Cross-entity conflict: another candidate in a DIFFERENT ICD-10 family matches the
    # header at least as well as the top. That's a genuine disagreement about WHICH
    # condition is being coded — most importantly a stale chart code vs the encounter's
    # documented code (e.g. active-problem F32.1 "single episode" vs Nabla F33.1
    # "recurrent" for a header that says "recurrent"). Never auto-pick the chart code
    # over the documented one; surface both with provenance and let the provider choose.
    top_root = _icd10_family_root(top.code)
    top_bucket = _overlap_bucket(header, top.display)
    for other in ranked[1:]:
        if _icd10_family_root(other.code) != top_root and _overlap_bucket(header, other.display) >= top_bucket:
            return None, True

    # An active problem-list match (with no cross-family conflict above) is trusted
    # for continuity of care.
    if top.source == CandidateSource.ACTIVE_PROBLEM:
        return top, False

    # If a second candidate ties the top through the meaningful tiers (1..4 — i.e.
    # only specificity/order separate them), it's genuinely ambiguous; surface both.
    if len(ranked) >= 2:
        second = ranked[1]
        if _sort_key(header, top)[:4] == _sort_key(header, second)[:4]:
            return None, True

    return top, False


def build_block_candidates(
    block_id: str,
    header: str,
    nabla_for_block: list[dict[str, Any]],
    chart: list[PatientConditionSnapshot],
    science_search: ScienceSearch | None = None,
) -> BlockCandidates:
    """Assemble → rank → resolve for one block, in one call (the belt's entry point)."""
    ranked = rank_candidates(header, assemble_block_candidates(header, nabla_for_block, chart, science_search))
    chosen, ambiguous = resolve_choice(header, ranked)
    return BlockCandidates(block_id=block_id, header=header, candidates=ranked, chosen=chosen, ambiguous=ambiguous)


def expand_unspecified(
    chosen: DiagnosisCandidate,
    science_search: ScienceSearch | None,
) -> list[DiagnosisCandidate]:
    """Return more-specific children of an unspecified ``chosen`` code.

    Used for the "Unspecified — consider refining" nudge: the working code stays
    applied, but the provider is offered grounded, more-specific siblings from the
    same ICD-10 family (looked up via the science service). Returns ``[]`` when no
    search is available or nothing more specific is found.
    """
    if science_search is None:
        return []
    norm = icd10_normalize(chosen.code)
    root = _icd10_family_root(norm)
    if not root:
        return []
    # Scope the refinements to the unspecified code's own sub-category, not the whole
    # 3-char family. ``G47.00`` ("Insomnia, unspecified") sits under ``G47.0`` (insomnia)
    # within the broader ``G47`` (all sleep disorders) — so its refinements are
    # ``G47.0x`` (G47.01/.09), NOT ``G47.33`` sleep apnea or ``G47.63`` bruxism. When the
    # 4th char is itself the unspecified marker ``9`` (``E03.9``, ``F33.9``, ``E11.9``),
    # the whole 3-char family IS the sub-category, so the root is the right scope.
    scope_prefix = norm[:4] if len(norm) >= 4 and norm[3] != "9" else root
    try:
        hits = science_search([root]) or []
    except Exception:
        return []
    children: list[DiagnosisCandidate] = []
    seen: set[str] = {norm}
    for hit in hits:
        code = icd10_normalize(getattr(hit, "code", ""))
        display = getattr(hit, "label", "")
        if not code or code in seen:
            continue
        # Within the unspecified code's sub-category, and itself a specified code. We do
        # NOT use "longer code = more specific": an unspecified bucket like ``G47.00`` has
        # equally-long specified siblings (``G47.01``, ``G47.09``).
        if not code.startswith(scope_prefix) or is_unspecified_code(code, display):
            continue
        seen.add(code)
        children.append(
            DiagnosisCandidate(
                code=code,
                raw_code=getattr(hit, "code", ""),
                display=getattr(hit, "label", ""),
                source=CandidateSource.MORE_SPECIFIC,
            )
        )
    return children
