"""Shared medication resolution for the scribe recommenders.

Both the medication-statement and prescription recommenders extract a
``medication_name`` (which the LLM is instructed to include the strength in,
e.g. ``"Lisinopril 20 mg"``) plus a comma-separated ``keywords`` list for the
FDB lookup. Historically each recommender resolved that to an FDB code by
searching CanvasScience for a bare keyword and blindly taking ``results[0]``.

That dropped the strength entirely: a note saying "Lisinopril 20 mg" would
search "lisinopril", get back whatever strength FDB ranked first (commonly the
10 mg group), and recommend *that* — the 20mg -> 10mg substitution providers
reported.

This module fixes the resolution step in one place:

1. It searches FDB with the full ``medication_name`` first (so the stated
   strength is in the candidate set FDB returns), then falls back to the
   keywords.
2. It selects the candidate whose description carries the *same strength* as
   the stated medication, instead of the first row returned. It only falls back
   to the first candidate when no strength match is found (or no strength was
   stated).

The selection is deterministic (no extra LLM round-trip): strengths are
normalized tokens like ``"20mg"`` extracted from both the stated name and each
candidate description, and a candidate matches when it contains every strength
the provider stated.
"""

from __future__ import annotations

import re

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.structures.medication_detail import MedicationDetail

# A strength is a number (optionally decimal, optionally a hyphen/slash-joined
# compound like "20-12.5" for combination products) followed by a dosage unit.
# We capture the whole "<number><unit>" token so matching is exact and "20 mg"
# never matches "120 mg" or "2.5 mg".
_STRENGTH_RE = re.compile(
    r"(\d+(?:\.\d+)?(?:\s*[-/]\s*\d+(?:\.\d+)?)*)\s*"
    r"(mcg|mg|g|ml|%|iu|meq|units?)\b",
    re.IGNORECASE,
)

# Tokens the LLM emits for the required `sig` field when the note states no
# directions. The recommendation schema forces a string, so the model fills it
# with a placeholder rather than leaving it empty.
_SIG_PLACEHOLDERS = {"unknown", "unk", "n/a", "na", "none", "null", "-", "tbd", "?"}


def sanitize_sig(sig: str | None) -> str:
    """Return the sig directions, blanking out LLM placeholder values.

    A blank sig is rendered as no directions line in the scribe UI (and stored
    as ``None`` on the command), instead of literal placeholder text like
    "<UNKNOWN>". Any value wholly wrapped in angle brackets (``<...>``) is
    treated as a placeholder, as are the known no-value tokens.
    """
    if sig is None:
        return ""
    cleaned = sig.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return ""
    if cleaned.lower() in _SIG_PLACEHOLDERS:
        return ""
    return cleaned


def extract_strengths(text: str) -> set[str]:
    """Return the normalized strength tokens found in ``text``.

    "Lisinopril 20 mg tablet" -> {"20mg"}; "20 MG" and "20mg" both normalize to
    "20mg"; combination strengths keep their joined form ("20-12.5mg").
    """
    result: set[str] = set()
    for amount, unit in _STRENGTH_RE.findall(text or ""):
        normalized_amount = re.sub(r"\s+", "", amount)
        result.add(f"{normalized_amount}{unit.lower()}")
    return result


def select_medication(medication_name: str, candidates: list[MedicationDetail]) -> MedicationDetail | None:
    """Pick the candidate matching the stated strength, else the first candidate."""
    if not candidates:
        return None
    wanted = extract_strengths(medication_name)
    if wanted:
        for candidate in candidates:
            if wanted.issubset(extract_strengths(candidate.description)):
                return candidate
    return candidates[0]


def resolve_medication_detail(
    medication_name: str,
    keywords: str,
    cache: dict[str, list[MedicationDetail]] | None = None,
) -> MedicationDetail | None:
    """Resolve a stated medication to the FDB candidate matching its strength.

    Searches FDB with the full ``medication_name`` first, then each keyword,
    and returns the candidate whose description carries the same strength as the
    stated name. Falls back to the first candidate found when no strength match
    exists. ``cache`` memoizes the FDB search per expression across a single
    recommendation run.
    """
    if cache is None:
        cache = {}

    wanted = extract_strengths(medication_name)
    expressions = [medication_name] + keywords.split(",")

    first_candidate: MedicationDetail | None = None
    for expression in expressions:
        expression = expression.strip()
        if not expression:
            continue
        key = expression.lower()
        if key not in cache:
            cache[key] = CanvasScience.medication_details([expression])
        candidates = cache[key]
        if not candidates:
            continue
        if first_candidate is None:
            first_candidate = candidates[0]
        if not wanted:
            return candidates[0]
        for candidate in candidates:
            if wanted.issubset(extract_strengths(candidate.description)):
                return candidate

    return first_candidate
