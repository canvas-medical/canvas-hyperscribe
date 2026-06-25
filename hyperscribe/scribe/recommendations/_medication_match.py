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
import unicodedata

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.structures.medication_detail import MedicationDetail

# A strength is a number followed by a dosage unit. The number may carry comma
# thousands separators ("1,000") and may be a hyphen/slash-joined compound that
# shares one unit ("20-12.5 mg", "160/4.5 mcg") for combination products. Each
# component is normalized to an exact "<number><unit>" token so that "20 mg"
# never matches "120 mg" or "2.5 mg".
_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_STRENGTH_RE = re.compile(
    rf"({_NUMBER}(?:\s*[-/]\s*{_NUMBER})*)\s*"
    r"(mcg|mg|g|ml|%|iu|meq|units?)\b",
    re.IGNORECASE,
)

# Tokens the LLM emits for the required `sig` field when the note states no
# directions. The recommendation schema forces a string, so the model fills it
# with a placeholder rather than leaving it empty.
_SIG_PLACEHOLDERS = {"unknown", "unk", "n/a", "na", "none", "null", "-", "tbd", "?"}

# The note-generation LLM frequently emits typographic Unicode (en/em dashes in
# "days 2–5", smart quotes, ellipses, non-breaking spaces) that the Surescripts
# NewRx wire format rejects — ``canvas_core``'s prescribe schema (mirrored in
# ``scribe/commands/_rx_validation.py``) only allows printable ASCII, so an
# unfolded sig fails the REVIEW step and rolls back the whole prescription.
# Map the common offenders to ASCII equivalents BEFORE the catch-all strip so a
# replacement is never silently dropped. The micro sign is handled explicitly —
# stripping it would turn "µg" into "g", a 1000x dosing error — and maps to "mc"
# so "µg" -> "mcg".
_SIG_UNICODE_REPLACEMENTS = {
    "‐": "-",
    "‑": "-",
    "‒": "-",
    "–": "-",
    "—": "-",
    "―": "-",
    "‘": "'",
    "’": "'",
    "‚": "'",
    "‛": "'",
    "“": '"',
    "”": '"',
    "„": '"',
    "…": "...",
    " ": " ",
    " ": " ",
    " ": " ",
    " ": " ",
    "µ": "mc",
    "μ": "mc",  # micro sign / Greek mu -> "mc" so "µg" -> "mcg"
}


def ascii_fold_sig(text: str) -> str:
    """Fold a sig to printable ASCII so it survives Surescripts validation.

    Applies known typographic replacements first, then NFKD-decomposes accents
    and drops any residual non-ASCII. Mirrors the allowed set in
    ``_rx_validation._RE_INVALID_CHARACTERS`` (space through tilde).
    """
    for unicode_char, replacement in _SIG_UNICODE_REPLACEMENTS.items():
        text = text.replace(unicode_char, replacement)
    text = unicodedata.normalize("NFKD", text)
    return text.encode("ascii", "ignore").decode("ascii")


def sanitize_sig(sig: str | None) -> str:
    """Return the sig directions, blanking placeholders and folding to ASCII.

    A blank sig is rendered as no directions line in the scribe UI (and stored
    as ``None`` on the command), instead of literal placeholder text like
    "<UNKNOWN>". Any value wholly wrapped in angle brackets (``<...>``) is
    treated as a placeholder, as are the known no-value tokens. Surviving
    directions are folded to printable ASCII so they pass Surescripts'
    sig validation downstream.
    """
    if sig is None:
        return ""
    cleaned = sig.strip()
    if cleaned.startswith("<") and cleaned.endswith(">"):
        return ""
    if cleaned.lower() in _SIG_PLACEHOLDERS:
        return ""
    return ascii_fold_sig(cleaned)


def extract_strengths(text: str) -> set[str]:
    """Return the normalized strength tokens found in ``text``.

    "Lisinopril 20 mg tablet" -> {"20mg"}; "20 MG", "20mg" and "1,000 mg" all
    normalize (commas stripped, "units" folded to "unit"). A combination strength
    is split into one token per component sharing the unit, so both the stated
    "Symbicort 160/4.5 mcg" and FDB's "160 mcg-4.5 mcg/actuation" yield
    {"160mcg", "4.5mcg"} and therefore match.
    """
    result: set[str] = set()
    for amount, unit in _STRENGTH_RE.findall(text or ""):
        unit_normalized = "unit" if unit.lower() == "units" else unit.lower()
        for component in re.split(r"[-/]", amount):
            number = re.sub(r"[\s,]", "", component)
            if number:
                result.add(f"{number}{unit_normalized}")
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
