"""Grounded ICD-10 suggestions for uncoded condition headers.

This REPLACES the former free-generation path, in which the LLM emitted ICD-10
codes that were only existence-checked — a hallucination risk (a plausible but
clinically-wrong code that happens to exist would pass). Codes now come ONLY from
the Canvas science service and are ranked by the shared deterministic engine
(``diagnosis_candidates``). No LLM is involved, so a code that the ontology does
not return can never be surfaced.

In the main ``/generate-summary`` flow these options are produced inline by the
A&P belt (``split_plan_into_diagnoses`` stamps ``candidate_suggestions`` on each
uncoded diagnose proposal, keyed by ``block_id``). This module backs the
standalone ``/suggest-diagnoses`` endpoint, which resolves a list of free-text
condition headers to grounded, ranked code options.
"""

from __future__ import annotations

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.scribe.commands.diagnosis_candidates import build_block_candidates, serialize_candidate


def suggest_diagnoses(conditions: list[str]) -> dict[str, list[dict[str, str]]]:
    """Return ``{condition_text: [ranked grounded code options]}``.

    Each option is grounded in a Canvas science-service search for the condition
    text and carries ``{code, formatted_code, display, provenance}``. No code is
    invented: a condition with no science match yields an empty list (the provider
    falls back to manual search). Blank conditions are skipped.
    """
    result: dict[str, list[dict[str, str]]] = {}
    for condition in conditions:
        if not (condition or "").strip():
            continue
        block = build_block_candidates(
            block_id="",
            header=condition.strip(),
            nabla_for_block=[],
            chart=[],
            science_search=CanvasScience.search_conditions,
        )
        result[condition] = [serialize_candidate(candidate) for candidate in block.candidates[:5]]
    return result
