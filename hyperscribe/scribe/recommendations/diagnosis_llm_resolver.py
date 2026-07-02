"""Grounded-LLM resolver for uncoded A&P diagnosis blocks.

The deterministic belt (``ap_split`` / ``diagnosis_candidates``) leaves a block
uncoded when neither Nabla nor the patient chart supplied a code and the lexical
science-search fallback found nothing useful (or found a clinically wrong lexical
match). This module resolves those blocks with a **retrieval-augmented, grounded**
LLM step — the same "oracle over a retrieved set" pattern as
``libraries/selector_chat.SelectorChat.condition_from``, extended with an adaptive
query-expansion round.

Per uncoded block (at most ``_MAX_ROUNDS`` LLM calls, usually one):

1. Show the LLM the block header + assessment body + the candidate ICD-10 codes the
   belt already assembled. It returns a :class:`DiagnosisResolutionStep`: a selection
   from the provided list, a confidence, a ranked shortlist, and — when nothing
   provided fits — clinical ``more_search_terms``.
2. If it returns search terms and made no selection, retrieve real codes via
   ``science_search`` (Canvas science service), merge them into the candidate pool,
   and ask again.

**Anti-hallucination is structural**: the LLM may only choose codes that are present
in the retrieved pool; any code it returns that is not in the pool is dropped. No code
is ever invented. Everything is best-effort — any failure returns no resolution for
that block, leaving the belt's deterministic output untouched.
"""

from __future__ import annotations

import json
from http import HTTPStatus
from typing import Any, Callable, NamedTuple

from logger import log

from hyperscribe.scribe.commands.diagnosis_candidates import format_icd10, icd10_normalize
from hyperscribe.scribe.recommendations.schemas import DiagnosisResolutionStep

# Injected callables (kept abstract so tests can supply fakes/mocks).
ScienceSearch = Callable[[list[str]], list[Any]]
ClientFactory = Callable[[], Any]

_MAX_ROUNDS = 2
_MAX_SUGGESTIONS = 6

_SYSTEM_PROMPT = (
    "You are a clinical coding assistant. You are given one problem from a note's assessment "
    "& plan and a list of candidate ICD-10 codes retrieved from a medical ontology. Choose the "
    "single ICD-10 code that best matches the DOCUMENTED clinical picture, taking the full "
    "assessment text into account (labs, findings, and the DIRECTION of any abnormality). "
    "You may ONLY choose codes from the provided candidate list — never invent, modify, or "
    "reformat a code. Copy codes verbatim. "
    "If none of the provided candidates fit the documented picture, do NOT force a choice: "
    "leave selected_code null and return `more_search_terms` with the precise clinical term(s) "
    "or differential to look up — e.g. the specific diagnosis, a synonym, or the correct "
    "direction (return 'hypoalbuminemia', never 'hyperalimentation', for a low-albumin note). "
    "A condition that is being actively managed, treated, or monitored is STILL a current "
    "diagnosis to code, even when today's labs or vitals are normal BECAUSE of that treatment — "
    "code the underlying condition being managed, not 'normal'. For example, ongoing "
    "prescription-strength vitamin D supplementation implies vitamin D deficiency (a normal level "
    "on supplementation means it is controlled, not absent); a chronic disease that is 'well "
    "controlled' on medication is still that disease. When the header names a treatment/"
    "supplement rather than the diagnosis, search for the condition that treatment manages. "
    "A purely administrative or logistical header with no underlying clinical condition (e.g. an "
    "access or scheduling problem) should return low confidence with no selection."
)


class BlockContext(NamedTuple):
    """One uncoded diagnose block handed to the resolver."""

    block_id: str
    header: str
    body: str
    # The belt's already-assembled suggestions (serialize_candidate shape:
    # ``{code, formatted_code, display, provenance}``); may be empty.
    candidates: list[dict[str, str]]


class BlockResolution(NamedTuple):
    """The resolver's grounded outcome for one block.

    ``chosen`` is ``(formatted_code, display)`` only on a high-confidence single match
    (the caller auto-applies it). ``suggestions`` is the ranked, in-pool picker list
    (serialize_candidate shape). Both grounded — never an invented code.
    """

    chosen: tuple[str, str] | None
    confidence: str
    suggestions: list[dict[str, str]]


def _pool_entry(code: str, formatted_code: str, display: str, provenance: str) -> dict[str, str]:
    return {"code": code, "formatted_code": formatted_code, "display": display, "provenance": provenance}


def _build_user_prompt(block: BlockContext, pool: dict[str, dict[str, str]]) -> str:
    lines = [
        "Problem (assessment & plan header):",
        block.header or "(none)",
        "",
        "Full assessment text:",
        block.body or "(none)",
        "",
        "Candidate ICD-10 codes — you may ONLY select from these:",
    ]
    if pool:
        for meta in pool.values():
            lines.append(f" * {meta['formatted_code']} — {meta['display']}")
    else:
        lines.append(" (none retrieved yet — return more_search_terms)")
    lines += [
        "",
        "Select the single best-matching code (selected_code) and rank the most relevant "
        "candidates (ranked_codes), copying each verbatim from the list above. If none fit the "
        "documented picture, leave selected_code null and provide more_search_terms.",
    ]
    return "\n".join(lines)


def _ask(block: BlockContext, pool: dict[str, dict[str, str]], client: Any) -> DiagnosisResolutionStep | None:
    """One structured LLM call. Returns None (best-effort) on any transport/parse failure."""
    client.reset_prompts()
    client.set_system_prompt([_SYSTEM_PROMPT])
    client.set_user_prompt([_build_user_prompt(block, pool)])
    client.set_schema(DiagnosisResolutionStep)
    try:
        response = client.request()
    except Exception:
        log.exception("LLM request failed for diagnosis resolution")
        return None
    if response.code != HTTPStatus.OK:
        # Do not log response.response: it is derived from the note and may contain PHI.
        log.info(f"LLM returned {response.code} for diagnosis resolution")
        return None
    try:
        parsed: DiagnosisResolutionStep = DiagnosisResolutionStep.model_validate(json.loads(response.response))
    except Exception:
        log.exception("Failed to parse diagnosis resolution response")
        return None
    return parsed


def _merge_science(terms: list[str], pool: dict[str, dict[str, str]], science_search: ScienceSearch) -> bool:
    """Retrieve real codes for ``terms`` and add any new ones to ``pool``. Returns True if added."""
    added = False
    try:
        hits = science_search([t for t in terms if (t or "").strip()]) or []
    except Exception:
        # Best-effort: a science outage must not break resolution.
        return False
    for hit in hits:
        norm = icd10_normalize(getattr(hit, "code", ""))
        if not norm or norm in pool:
            continue
        pool[norm] = _pool_entry(
            code=getattr(hit, "code", "") or norm,
            formatted_code=format_icd10(norm),
            display=getattr(hit, "label", "") or "",
            provenance="ICD-10 search",
        )
        added = True
    return added


def _suggestions_from(step: DiagnosisResolutionStep, pool: dict[str, dict[str, str]]) -> list[dict[str, str]]:
    """Build the ranked, in-pool picker list from the model's ranked_codes (+ selection first).

    Hard anti-hallucination gate: only codes present in ``pool`` survive.
    """
    ordered: list[str] = []
    for code in [step.selected_code, *step.ranked_codes]:
        norm = icd10_normalize(code or "")
        if norm and norm in pool and norm not in ordered:
            ordered.append(norm)
    return [dict(pool[norm]) for norm in ordered[:_MAX_SUGGESTIONS]]


def _resolve_one(block: BlockContext, client: Any, science_search: ScienceSearch) -> BlockResolution | None:
    # Seed the pool from the belt's existing suggestions, keyed by normalized code.
    pool: dict[str, dict[str, str]] = {}
    for candidate in block.candidates or []:
        norm = icd10_normalize(candidate.get("code") or candidate.get("formatted_code") or "")
        if not norm or norm in pool:
            continue
        pool[norm] = _pool_entry(
            code=candidate.get("code") or norm,
            formatted_code=candidate.get("formatted_code") or format_icd10(norm),
            display=candidate.get("display") or "",
            provenance=candidate.get("provenance") or "Detected in note",
        )

    last_step: DiagnosisResolutionStep | None = None
    for _round in range(_MAX_ROUNDS):
        step = _ask(block, pool, client)
        if step is None:
            break
        last_step = step
        selected_norm = icd10_normalize(step.selected_code or "")
        if selected_norm and selected_norm in pool:
            entry = pool[selected_norm]
            suggestions = _suggestions_from(step, pool)
            # Auto-apply only on high confidence; otherwise surface for the provider.
            chosen = (entry["formatted_code"], entry["display"]) if step.confidence == "high" else None
            return BlockResolution(chosen=chosen, confidence=step.confidence, suggestions=suggestions)
        # No valid in-pool selection: expand the search and try once more.
        if not _merge_science(step.more_search_terms, pool, science_search):
            break

    # Exhausted rounds without a confident selection. Surface whatever the last step
    # ranked (in-pool) so the provider still gets grounded options; else give up.
    if last_step is not None:
        suggestions = _suggestions_from(last_step, pool)
        if suggestions:
            return BlockResolution(chosen=None, confidence=last_step.confidence, suggestions=suggestions)
    return None


def resolve_uncoded_blocks(
    blocks: list[BlockContext],
    make_client: ClientFactory,
    science_search: ScienceSearch,
) -> dict[str, BlockResolution]:
    """Resolve each uncoded block. Returns ``{block_id: BlockResolution}``.

    A fresh client is built per block (mirrors ``recommend_commands``). Every block is
    best-effort: a failure logs and is skipped, so a block simply keeps the belt's
    deterministic output.
    """
    results: dict[str, BlockResolution] = {}
    for block in blocks:
        try:
            resolution = _resolve_one(block, make_client(), science_search)
        except Exception:
            log.exception("diagnosis resolution failed for a block")
            resolution = None
        if resolution is not None:
            results[block.block_id] = resolution
    return results
