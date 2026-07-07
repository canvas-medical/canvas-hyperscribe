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
from decimal import Decimal

from hyperscribe.libraries.canvas_science import CanvasScience
from hyperscribe.structures.medication_detail import MedicationDetail

# A strength is a number followed by a dosage unit. The number may carry comma
# thousands separators ("1,000") and may be a hyphen/slash-joined compound that
# shares one unit ("20-12.5 mg", "160/4.5 mcg") for combination products. Each
# component is normalized to an exact "<number><unit>" token so that "20 mg"
# never matches "120 mg" or "2.5 mg".
#
# Units may be abbreviated ("mcg", "mg") or spelled out in the note ("micrograms",
# "milligrams") — the extraction prompt preserves the note's wording, so both must
# parse. The spelled-out alternatives are listed BEFORE the single-letter
# abbreviations because ``re`` takes the first matching alternative at a position,
# not the longest; otherwise "micrograms" would partially match as "gram"/"g".
#
# The optional trailing "/<denom>" (e.g. "units/mL", "units/day") is captured so
# the units family can tell a per-dose amount ("30 units") apart from a
# concentration / rate ("100 units/mL", "30 units/day") — see ``_strength_token``.
# It only matches an alphabetic denominator, so a numeric concentration like
# "250 mg/5 mL" is left untouched (its "5 mL" still parses as its own token).
_NUMBER = r"\d[\d,]*(?:\.\d+)?"
_STRENGTH_RE = re.compile(
    rf"(?P<amount>{_NUMBER}(?:\s*[-/]\s*{_NUMBER})*)\s*"
    r"(?P<unit>micrograms?|milligrams?|milliliters?|grams?|units?|mcg|mg|ml|g|%|iu|meq)"
    r"(?:\s*/\s*(?P<denom>[a-zA-Z]+))?\b",
    re.IGNORECASE,
)

# Spelled-out and plural unit forms fold to a canonical unit token.
_UNIT_ALIASES = {
    "micrograms": "mcg",
    "microgram": "mcg",
    "milligrams": "mg",
    "milligram": "mg",
    "grams": "g",
    "gram": "g",
    "milliliters": "ml",
    "milliliter": "ml",
    "units": "unit",
}

# The mass family is interconvertible, so strengths stated in different mass units
# match each other ("0.075 mg" == "75 mcg"). Every mass strength is canonicalized
# to micrograms before tokenizing. ml / % / iu / meq / unit each stay in their own
# (non-interconverting) family.
_MASS_TO_MCG = {"mcg": Decimal(1), "mg": Decimal(1000), "g": Decimal(1000000)}


def _format_number(value: Decimal) -> str:
    """Render a Decimal trailing-zero- and exponent-free ("2E+4" -> "20000").

    Mirrors the formatting idiom in ``_dosage._format_decimal``; kept local to
    avoid importing from ``_dosage`` (which imports from this module).
    """
    return format(value.normalize(), "f")


def _strength_token(number: str, unit: str, denom: str | None) -> str | None:
    """Build one normalized strength token, or None if the number is unparseable.

    Mass units canonicalize to micrograms; the units family appends the
    concentration/rate denominator when present so a bare per-dose "30 units"
    cannot match a "30 units/day" or "100 units/mL" product.
    """
    try:
        value = Decimal(number)
    except (ArithmeticError, ValueError):
        return None
    if not value.is_finite():
        return None
    if unit in _MASS_TO_MCG:
        return f"{_format_number(value * _MASS_TO_MCG[unit])}mcg"
    if unit == "unit" and denom:
        return f"{_format_number(value)}unit/{denom.lower()}"
    return f"{_format_number(value)}{unit}"


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

    Maps the common typographic offenders (dashes, smart quotes, ellipsis,
    non-breaking spaces, the micro sign) to ASCII, then drops any residual
    non-ASCII. Mirrors the allowed set in
    ``_rx_validation._RE_INVALID_CHARACTERS`` (space through tilde).

    NOTE: ``unicodedata`` is not an allowed import in the Canvas plugin sandbox,
    so accent folding (e.g. "é" -> "e") is not attempted — residual accented
    characters are simply dropped. This is fine for prescription sigs, which are
    ASCII in practice; the explicit map covers the cases the note LLM actually
    produces.
    """
    for unicode_char, replacement in _SIG_UNICODE_REPLACEMENTS.items():
        text = text.replace(unicode_char, replacement)
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

    "Lisinopril 20 mg tablet" -> {"20000mcg"}; abbreviated and spelled-out units
    ("20 mg", "20 milligrams"), case, and comma separators all normalize, and the
    mass family is expressed in micrograms so "0.075 mg" and "75 mcg" yield the
    same token. A combination strength is split into one token per component
    sharing the unit, so both the stated "Symbicort 160/4.5 mcg" and FDB's
    "160 mcg-4.5 mcg/actuation" yield {"160mcg", "4.5mcg"} and therefore match.
    """
    result: set[str] = set()
    for match in _STRENGTH_RE.finditer(text or ""):
        unit = _UNIT_ALIASES.get(match.group("unit").lower(), match.group("unit").lower())
        denom = match.group("denom")
        for component in re.split(r"[-/]", match.group("amount")):
            number = re.sub(r"[\s,]", "", component)
            if not number:
                continue
            token = _strength_token(number, unit, denom)
            if token:
                result.add(token)
    return result


def _matching_candidate(wanted: set[str], candidates: list[MedicationDetail]) -> MedicationDetail | None:
    """Return the first candidate carrying every wanted strength, else None."""
    for candidate in candidates:
        if wanted.issubset(extract_strengths(candidate.description)):
            return candidate
    return None


def select_medication(medication_name: str, candidates: list[MedicationDetail]) -> MedicationDetail | None:
    """Pick the candidate matching the stated strength.

    When the stated name carries no strength, fall back to the first candidate.
    When a strength WAS stated but no candidate carries it, return None rather
    than a candidate of a different strength — a wrong documented strength is a
    safety issue, so the medication is left unresolved for the provider.
    """
    if not candidates:
        return None
    wanted = extract_strengths(medication_name)
    if not wanted:
        return candidates[0]
    return _matching_candidate(wanted, candidates)


def resolve_medication_detail(
    medication_name: str,
    keywords: str,
    cache: dict[str, list[MedicationDetail]] | None = None,
) -> MedicationDetail | None:
    """Resolve a stated medication to the FDB candidate matching its strength.

    Searches FDB with the full ``medication_name`` first, then each keyword. When
    the stated name carries no strength, returns the first candidate found. When a
    strength WAS stated, returns the candidate carrying it; if no candidate across
    any expression carries the stated strength, returns None (the medication is
    left unresolved for the provider) instead of a wrong-strength candidate.
    ``cache`` memoizes the FDB search per expression across a single
    recommendation run.
    """
    if cache is None:
        cache = {}

    wanted = extract_strengths(medication_name)
    expressions = [medication_name] + keywords.split(",")

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
        if not wanted:
            return candidates[0]
        match = _matching_candidate(wanted, candidates)
        if match is not None:
            return match

    return None
