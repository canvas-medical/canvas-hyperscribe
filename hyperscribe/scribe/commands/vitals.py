from __future__ import annotations

import re
from typing import Any, NamedTuple

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.vitals import VitalsCommand

from hyperscribe.scribe.backend.models import CommandProposal, Observation
from hyperscribe.scribe.commands.base import CommandParser


# Refusal-reason categories. The category is reported via the
# ``VITALS_FIELD_REFUSED`` audit event in ``post_generate_summary`` so we
# can distinguish *why* a field was dropped (out-of-range vs ambiguous unit
# vs partial BP) without leaking the value itself. Strategist-flagged: the
# parser used to drop real-but-extreme clinical values silently; surfacing
# the refusal lets ops/clinical teams notice when a clinician really did
# observe HR=25 or SpO2=10 and the parser refused it.
REFUSAL_REASON_OUT_OF_RANGE = "out_of_range"
REFUSAL_REASON_AMBIGUOUS_UNIT = "ambiguous_unit"
REFUSAL_REASON_ATOMIC_BP_PARTIAL = "atomic_bp_partial"


class _Refusal(NamedTuple):
    """A single field-refusal record. Field names + reason only — NO VALUES (PHI)."""

    field: str
    reason: str


class VitalsExtractionResult(NamedTuple):
    """Result of vitals extraction with telemetry data attached.

    Returned by ``VitalsParser.extract_with_telemetry`` for callers that
    need both the proposal AND audit metadata (refusals + provenance).
    The plain ``extract_with_observations`` API stays available for callers
    that only need the proposal.

    ``source`` is one of ``"observations" | "regex" | "both" | "none"`` and
    reflects the FINAL proposal's surviving fields, not the raw inputs.
    Risk-hunter flagged: classifying off raw inputs marks the source as
    ``observations`` even when Nabla's BP-panel was fully refused, which
    inflates the telemetry signal for the observation path.
    """

    proposal: CommandProposal | None
    refusals: list[_Refusal]
    source: str


# LOINC codes for the vitals fields VitalsCommand exposes.
# Source: https://loinc.org/, cross-checked against the Nabla normalized-data API.
_LOINC_BP_PANEL = "85354-9"  # Blood pressure panel — value is "systole/diastole".
_LOINC_BP_SYSTOLE = "8480-6"
_LOINC_BP_DIASTOLE = "8462-4"
_LOINC_PULSE = "8867-4"
_LOINC_RESP_RATE = "9279-1"
_LOINC_O2_SAT = "2708-6"
_LOINC_O2_SAT_PULSE_OX = "59408-5"  # SpO2 via pulse oximetry — Nabla sometimes uses this code.
_LOINC_BODY_TEMP = "8310-5"
_LOINC_HEIGHT = "8302-2"
_LOINC_WEIGHT = "29463-7"

# Codes whose value we treat as a single scalar to write into ``_FIELD``.
# Iteration order is fixed (tuple) so behavior is deterministic when an
# observation carries multiple mapped LOINC codes — the auditor + risk-hunter
# both flagged the previous ``set`` iteration as non-deterministic.
_LOINC_TO_FIELD: tuple[tuple[str, str], ...] = (
    (_LOINC_BP_SYSTOLE, "blood_pressure_systole"),
    (_LOINC_BP_DIASTOLE, "blood_pressure_diastole"),
    (_LOINC_PULSE, "pulse"),
    (_LOINC_RESP_RATE, "respiration_rate"),
    (_LOINC_O2_SAT, "oxygen_saturation"),
    (_LOINC_O2_SAT_PULSE_OX, "oxygen_saturation"),
    (_LOINC_BODY_TEMP, "body_temperature"),
    (_LOINC_HEIGHT, "height"),
    (_LOINC_WEIGHT, "weight_lbs"),
)

# Fields whose numeric value is a float (the rest are ints).
_FLOAT_FIELDS: frozenset[str] = frozenset({"body_temperature"})

# Recognised unit synonyms. An unrecognised non-empty unit on a field with
# ambiguous magnitudes (temp °C vs °F, weight kg vs lbs, height cm vs in)
# triggers a range-based plausibility gate instead of a silent assumption.
_CELSIUS_UNITS: frozenset[str] = frozenset({"c", "°c", "degc", "celsius", "deg c"})
_FAHRENHEIT_UNITS: frozenset[str] = frozenset({"f", "°f", "degf", "fahrenheit", "deg f"})
_KG_UNITS: frozenset[str] = frozenset({"kg", "kgs", "kilogram", "kilograms"})
_LBS_UNITS: frozenset[str] = frozenset({"lb", "lbs", "pound", "pounds"})
_CM_UNITS: frozenset[str] = frozenset({"cm", "centimeter", "centimeters"})
_M_UNITS: frozenset[str] = frozenset({"m", "meter", "meters"})
_IN_UNITS: frozenset[str] = frozenset({"in", "inch", "inches", '"'})

# Plausible-value gates. A field is REFUSED (returned as None, not written)
# when the parsed value falls outside this window. The clinical principle:
# a missing field is recoverable on the next sync; a corrupted field that
# silently propagates into the chart is not.
#
# The parser matches the Canvas SDK ``VitalsCommand`` pydantic bounds (see
# ``canvas_sdk/commands/commands/vitals.py``) exactly. The SDK is the
# canonical clinical floor/ceiling: anything outside its ``ge=``/``le=``
# constraints triggers a 4xx from ``/insert-commands`` and the clinician
# sees an opaque failure after hitting Approve. The parser refuses those
# same values up front so we never round-trip data the SDK will reject.
#
# The UI edit-form spinbutton bounds in ``static/vitals-row.js`` may be
# tighter than the SDK (a separate UX concern — e.g. the form may clamp
# SpO2 to 60-100 while the SDK accepts 60-100; the UI ceilings can move
# without recoding the parser). When the UI clamps tighter than the SDK,
# the clinician edits the value back into range on the form — no data is
# lost; only acutely-extreme clinical values that the SDK already accepts
# go through this parser without UI intervention.
#
# Any future tightening here must stay >= the SDK floor and <= the SDK
# ceiling, otherwise the parser starts refusing values the SDK would
# accept. Loosening past the SDK constraints reintroduces the prod failure
# mode this gate was added to stop.
#
# These bounds also reject the pathological cases the risk-hunter surfaced
# (Kelvin temperatures, BP 999/999, pulse 9999, SpO2 200%, etc.).
_FIELD_RANGES: dict[str, tuple[float, float]] = {
    "blood_pressure_systole": (30, 305),
    "blood_pressure_diastole": (20, 180),
    "pulse": (30, 250),
    "respiration_rate": (6, 60),
    "oxygen_saturation": (60, 100),
    "body_temperature": (85, 107),  # °F
    "height": (10, 108),  # inches
    "weight_lbs": (1, 1500),
}

# Plausibility windows for unit inference when the source unit is missing
# or unrecognised. Used to disambiguate °C/°F (which have no value overlap
# in normal clinical ranges so range-based inference is safe).
_TEMP_C_WINDOW = (30.0, 45.0)
_TEMP_F_WINDOW = (80.0, 115.0)

# Empty-unit ambiguity bands for weight (kg vs lbs) and height (cm vs in).
# Unlike temperature, the kg/lbs and cm/in ranges overlap in the middle of
# the human distribution: a value of 70 with no unit could be 70 kg (155
# lbs) or 70 lbs (32 kg child). The same applies to height: 65 could be
# 65 inches (5'5") or 65 cm (infant). When we can't tell, we REFUSE rather
# than silently guess — a missing field is recoverable on the next sync;
# a corrupted weight/height that propagates into the chart is not.
#
# Bands are chosen at the edges of overlap:
# - Weight 30-250: covers pediatric-adult kg AND adult lbs; refuse.
#   Below 30 the value cannot plausibly be lbs (would be a newborn,
#   which a typical scribe note context disambiguates); above 250 the
#   value cannot plausibly be kg (no adult is 250 kg = 551 lbs).
# - Height 30-80: covers adult cm AND tall adult inches; refuse.
#   Below 30 the value cannot plausibly be inches (toddler range);
#   above 80 the value cannot plausibly be cm (would be infant length).
# Outside the bands we still apply the field range gate (_FIELD_RANGES)
# so wildly out-of-range values stay rejected.
_WEIGHT_AMBIGUOUS_BAND = (30.0, 250.0)
_HEIGHT_AMBIGUOUS_BAND = (30.0, 80.0)


def _normalize_unit(unit: str) -> str:
    return unit.strip().lower()


def _coerce_field_value(field: str, value: float) -> int | float:
    """Coerce a numeric value to the type expected by VitalsCommand for ``field``."""
    if field in _FLOAT_FIELDS:
        return round(value, 1)
    return int(round(value))


def _record_refusal(refusals: list[_Refusal] | None, field: str, reason: str) -> None:
    """Append a refusal record to ``refusals`` if a sink was provided.

    The sink stays optional so existing callers (tests, internal helpers
    that don't care about telemetry) keep their thin contract. Only
    ``extract_with_telemetry`` threads a real list through.
    """
    if refusals is None:
        return
    # De-duplicate: a single field can be refused at most once per extraction.
    # _apply_observation may walk multiple LOINC codes for the same field and
    # also the regex/observation passes can both refuse; we want one entry
    # per refused field.
    for entry in refusals:
        if entry.field == field:
            return
    refusals.append(_Refusal(field=field, reason=reason))


def _validate_field(
    field: str,
    value: float,
    refusals: list[_Refusal] | None = None,
) -> int | float | None:
    """Range-gate ``value`` for ``field``. Returns the coerced value or None when implausible.

    Applied on BOTH the observation path and the regex path so a single discipline
    governs all writes to VitalsCommand. The Council called out that
    out-of-range BP/pulse/SpO2/etc. flow through both paths today; this is the
    single chokepoint that stops it.

    When ``refusals`` is provided, a refusal record is appended with reason
    ``out_of_range`` so ``post_generate_summary`` can emit a
    ``VITALS_FIELD_REFUSED`` audit event.
    """
    bounds = _FIELD_RANGES.get(field)
    if bounds is None:
        return _coerce_field_value(field, value)
    low, high = bounds
    if value < low or value > high:
        _record_refusal(refusals, field, REFUSAL_REASON_OUT_OF_RANGE)
        return None
    return _coerce_field_value(field, value)


def _convert_temperature_to_fahrenheit(
    value: float,
    unit: str,
    *,
    refusals: list[_Refusal] | None = None,
) -> float | None:
    """Convert ``value`` from any recognised temperature unit to °F.

    When the unit is missing/unrecognised, fall back to a plausibility window:
    a value in the °C range converts; a value in the °F range passes through;
    anything outside both windows (e.g., Kelvin 310, garbage) is refused.
    """
    if unit in _CELSIUS_UNITS:
        return value * 9.0 / 5.0 + 32.0
    if unit in _FAHRENHEIT_UNITS:
        return value
    # Unit unknown — infer from magnitude.
    if _TEMP_C_WINDOW[0] <= value <= _TEMP_C_WINDOW[1]:
        return value * 9.0 / 5.0 + 32.0
    if _TEMP_F_WINDOW[0] <= value <= _TEMP_F_WINDOW[1]:
        return value
    _record_refusal(refusals, "body_temperature", REFUSAL_REASON_AMBIGUOUS_UNIT)
    return None


def _convert_weight_to_lbs(
    value: float,
    unit: str,
    *,
    refusals: list[_Refusal] | None = None,
) -> float | None:
    """Convert ``value`` to lbs.

    With an explicit unit, convert normally — this is the typical Nabla path.
    With an empty/unrecognised unit, REFUSE values in the kg/lbs overlap band
    (30-250) because we can't tell which scale the source intended. Accept
    values outside the band as unambiguous lbs (the _FIELD_RANGES gate still
    enforces the final plausibility window).
    """
    if unit in _KG_UNITS:
        return value * 2.20462
    if unit in _LBS_UNITS:
        return value
    # Unit unknown — refuse inside the ambiguity band, accept as lbs outside it.
    if _WEIGHT_AMBIGUOUS_BAND[0] <= value <= _WEIGHT_AMBIGUOUS_BAND[1]:
        _record_refusal(refusals, "weight_lbs", REFUSAL_REASON_AMBIGUOUS_UNIT)
        return None
    return value


def _convert_height_to_inches(
    value: float,
    unit: str,
    *,
    refusals: list[_Refusal] | None = None,
) -> float | None:
    """Convert ``value`` to inches.

    With an explicit unit, convert normally — this is the typical Nabla path.
    With an empty/unrecognised unit, REFUSE values in the cm/in overlap band
    (30-80) because we can't tell which scale the source intended. Accept
    values outside the band as unambiguous inches (the _FIELD_RANGES gate
    still enforces the final plausibility window).
    """
    if unit in _CM_UNITS:
        return value * 0.393701
    if unit in _M_UNITS:
        return value * 39.3701
    if unit in _IN_UNITS:
        return value
    # Unit unknown — refuse inside the ambiguity band, accept as inches outside it.
    if _HEIGHT_AMBIGUOUS_BAND[0] <= value <= _HEIGHT_AMBIGUOUS_BAND[1]:
        _record_refusal(refusals, "height", REFUSAL_REASON_AMBIGUOUS_UNIT)
        return None
    return value


def _parse_numeric(value: str) -> float | None:
    """Pull the first numeric token out of a value string."""
    match = re.search(r"-?\d+(?:\.\d+)?", value)
    if match is None:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _coding_codes(observation: Observation) -> set[str]:
    """Return the LOINC codes attached to ``observation``."""
    codes: set[str] = set()
    for entry in observation.coding:
        # Nabla emits ``system`` in a few forms ("LOINC", "http://loinc.org", ""); filter
        # by membership in our known-code map instead of trusting the system string.
        if entry.code:
            codes.add(entry.code.strip())
    return codes


def _apply_observation(
    observation: Observation,
    result: dict[str, int | float | None],
    *,
    refusals: list[_Refusal] | None = None,
) -> None:
    """Merge a single observation into ``result`` if it maps to a known LOINC code."""
    codes = _coding_codes(observation)
    unit = _normalize_unit(observation.unit)
    raw_value = observation.value or ""

    # BP panel: value is "systole/diastole".
    if _LOINC_BP_PANEL in codes:
        bp_match = re.search(r"(\d+)\s*/\s*(\d+)", raw_value)
        if bp_match is not None:
            systole = _validate_field("blood_pressure_systole", float(bp_match.group(1)), refusals=refusals)
            diastole = _validate_field("blood_pressure_diastole", float(bp_match.group(2)), refusals=refusals)
            if systole is not None and result.get("blood_pressure_systole") is None:
                result["blood_pressure_systole"] = systole
            if diastole is not None and result.get("blood_pressure_diastole") is None:
                result["blood_pressure_diastole"] = diastole
        return

    # Single-scalar observations. Walk the LOINC map in declared priority
    # order so behavior is deterministic for observations that carry
    # multiple mapped codes. Note: do NOT early-return when conversion or
    # validation rejects a value — subsequent matching codes for the same
    # observation get a chance (e.g., 2708-6 and 59408-5 both map to
    # oxygen_saturation; one might be present in coding while another is not).
    for code, field in _LOINC_TO_FIELD:
        if code not in codes:
            continue
        if result.get(field) is not None:
            continue
        numeric = _parse_numeric(raw_value)
        if numeric is None:
            continue
        converted: float | None = numeric
        if field == "body_temperature":
            converted = _convert_temperature_to_fahrenheit(numeric, unit, refusals=refusals)
        elif field == "weight_lbs":
            converted = _convert_weight_to_lbs(numeric, unit, refusals=refusals)
        elif field == "height":
            converted = _convert_height_to_inches(numeric, unit, refusals=refusals)
        if converted is None:
            continue
        validated = _validate_field(field, converted, refusals=refusals)
        if validated is None:
            continue
        result[field] = validated


def _parse_observations(
    observations: list[Observation],
    *,
    refusals: list[_Refusal] | None = None,
) -> dict[str, int | float | None]:
    """Extract VitalsCommand fields from Nabla normalized observations."""
    result: dict[str, int | float | None] = {}
    for observation in observations:
        _apply_observation(observation, result, refusals=refusals)
    return result


# Display-string formatter. Mirrors the post-edit formatter in
# ``static/summary.js`` (the ``type === 'vitals'`` branch around L912) so the
# initial backend-emitted display matches what the UI rebuilds after every
# edit — no format flash on first save. The CRITICAL invariant is that this
# function reads ONLY from the validated ``data`` dict; any field refused by
# ``_validate_field`` is absent from ``data`` and therefore absent from the
# display. This prevents the prod failure mode where the parser dropped
# blood_pressure_systole=38 from data but Nabla's free-text "BP 38/22"
# remained in display, so the clinician approved a half-written BP. After
# this change, refused fields disappear from BOTH data and display.
def _format_vitals_display(data: dict[str, int | float | None]) -> str:
    """Build a canonical display string from the validated ``data`` dict.

    Reads ONLY from ``data``: any field refused by ``_validate_field`` is
    absent and therefore cannot appear in the display string. This is the
    contract the UAT failure surfaced: display must accurately describe data.
    """
    parts: list[str] = []
    systole = data.get("blood_pressure_systole")
    diastole = data.get("blood_pressure_diastole")
    if systole is not None and diastole is not None:
        parts.append(f"BP {systole}/{diastole} mmHg")
    pulse = data.get("pulse")
    if pulse is not None:
        parts.append(f"HR {pulse} bpm")
    respiration_rate = data.get("respiration_rate")
    if respiration_rate is not None:
        parts.append(f"RR {respiration_rate} /min")
    oxygen_saturation = data.get("oxygen_saturation")
    if oxygen_saturation is not None:
        parts.append(f"SpO2 {oxygen_saturation}%")
    body_temperature = data.get("body_temperature")
    if body_temperature is not None:
        # ``:g`` drops trailing ``.0`` so 99.0 → "99" (matches the JS template
        # literal in summary.js which renders the same after JSON round-trip
        # turns 99.0 into 99). Decimals like 98.6 stay as "98.6". Without
        # this, the backend emits "Temp 99.0 °F" but the JS rebuilds it as
        # "Temp 99 °F" on the first edit — a format flash that defeats the
        # whole reason this rebuild was added.
        parts.append(f"Temp {body_temperature:g} °F")
    height = data.get("height")
    if height is not None:
        parts.append(f"Height {height} in")
    weight_lbs = data.get("weight_lbs")
    if weight_lbs is not None:
        parts.append(f"Weight {weight_lbs} lbs")
    return ", ".join(parts)


def _set_if_valid(
    result: dict[str, int | float | None],
    field: str,
    value: float,
    *,
    refusals: list[_Refusal] | None = None,
) -> None:
    """Range-gated write to ``result[field]``. Skips the assignment when invalid."""
    validated = _validate_field(field, value, refusals=refusals)
    if validated is not None:
        result[field] = validated


def _parse_vitals(
    text: str,
    *,
    refusals: list[_Refusal] | None = None,
) -> dict[str, int | float | None]:
    """Parse free-text vitals into structured fields (fallback when observations are absent)."""
    result: dict[str, int | float | None] = {}
    for line in re.split(r"[,\n]", text):
        line = line.strip()
        if not line:
            continue
        # Blood pressure: ``120/80``.
        bp_match = re.search(r"(\d+)\s*/\s*(\d+)", line)
        if bp_match and "blood_pressure_systole" not in result:
            _set_if_valid(result, "blood_pressure_systole", float(bp_match.group(1)), refusals=refusals)
            _set_if_valid(result, "blood_pressure_diastole", float(bp_match.group(2)), refusals=refusals)
            continue
        # Pulse.
        m = re.search(r"(?:HR|Heart\s*rate|Pulse)[:\s]*(\d+)", line, re.IGNORECASE)
        if m:
            _set_if_valid(result, "pulse", float(m.group(1)), refusals=refusals)
            continue
        # Respiration rate — accept ``RR``, ``Resp``, ``Respiration``, ``Respiratory``,
        # ``Resp rate``, and other ``Resp*`` variants Nabla emits when transcribing speech.
        m = re.search(r"(?:RR|Resp[a-z]*(?:\s*rate)?)[:\s]*(\d+)", line, re.IGNORECASE)
        if m:
            _set_if_valid(result, "respiration_rate", float(m.group(1)), refusals=refusals)
            continue
        # O2 saturation — require either ``SpO2`` or an explicit ``sat[uration]``
        # qualifier so we don't capture flow rates like ``O2 2L NC`` (which
        # used to silently land as oxygen_saturation=2 — a documented prod
        # data-corruption mode). The optional ``(SpO2)`` parenthetical
        # handles Nabla's verbose ``Oxygen saturation (SpO2): 98%`` form.
        m = re.search(
            r"(?:SpO2\b|(?:O2|Oxygen)\s+sat(?:uration)?\b(?:\s*\(SpO2\))?)[\s,:]*(\d+)\s*%?",
            line,
            re.IGNORECASE,
        )
        if m:
            _set_if_valid(result, "oxygen_saturation", float(m.group(1)), refusals=refusals)
            continue
        # Temperature.
        m = re.search(r"Temp(?:erature)?[:\s]*([\d.]+)\s*°?\s*([cCfF])?", line, re.IGNORECASE)
        if m:
            value = float(m.group(1))
            scale = (m.group(2) or "").lower()
            if scale == "c":
                value = value * 9.0 / 5.0 + 32.0
            _set_if_valid(result, "body_temperature", value, refusals=refusals)
            continue
        # Height — stored in inches. Accept the typographic ``5'10"`` form,
        # the spoken ``5 ft 10 in`` / ``5 feet 10 inches`` / ``5 foot 10`` /
        # ``6 feet`` / ``70 in`` forms, AND metric ``cm``/``m``. ``\bheight\b``
        # anchors the line so we don't accidentally extract a height from a
        # ``70 inch`` pulse measurement description; metric forms keep
        # ``Height:`` for safety (cm/m alone is too easy to false-positive).
        if re.search(r"\bheight\b", line, re.IGNORECASE):
            feet_inches = re.search(
                r"(\d+)\s*(?:'|ft\b|foot\b|feet\b)\s*(\d+)\s*(?:\"|in\b|inch|inches)?",
                line,
                re.IGNORECASE,
            )
            feet_only = re.search(r"(\d+)\s*(?:'|ft\b|foot\b|feet\b)", line, re.IGNORECASE)
            inches_only = re.search(r"(\d+)\s*(?:\"|in\b|inch|inches)", line, re.IGNORECASE)
            if feet_inches:
                height_in = int(feet_inches.group(1)) * 12 + int(feet_inches.group(2))
                _set_if_valid(result, "height", float(height_in), refusals=refusals)
                continue
            if feet_only:
                _set_if_valid(result, "height", float(int(feet_only.group(1)) * 12), refusals=refusals)
                continue
            if inches_only:
                _set_if_valid(result, "height", float(int(inches_only.group(1))), refusals=refusals)
                continue
        # Height (metric: cm or m), only when ``Height:`` is the anchor.
        m = re.search(r"Height[:\s]*(\d+(?:\.\d+)?)\s*(cm|m)\b", line, re.IGNORECASE)
        if m:
            value = float(m.group(1))
            unit = m.group(2).lower()
            if unit == "cm":
                _set_if_valid(result, "height", value * 0.393701, refusals=refusals)
            else:
                _set_if_valid(result, "height", value * 39.3701, refusals=refusals)
            continue
        # Weight (lbs).
        m = re.search(r"Weight[:\s]*(\d+(?:\.\d+)?)\s*(?:lbs?|pounds?)", line, re.IGNORECASE)
        if m:
            _set_if_valid(result, "weight_lbs", float(m.group(1)), refusals=refusals)
            continue
        # Weight (kg).
        m = re.search(r"Weight[:\s]*(\d+(?:\.\d+)?)\s*(?:kg|kgs|kilograms?)", line, re.IGNORECASE)
        if m:
            _set_if_valid(result, "weight_lbs", float(m.group(1)) * 2.20462, refusals=refusals)
            continue
    return result


class VitalsParser(CommandParser):
    command_type = "vitals"

    def extract(self, text: str) -> CommandProposal | None:
        """Free-text fallback. Used when no structured observations are available."""
        return self.extract_with_observations(text, [])

    def extract_with_observations(
        self,
        text: str,
        observations: list[Observation],
    ) -> CommandProposal | None:
        """Prefer observations (LOINC + units); fall back to regex for any field they didn't cover.

        Thin wrapper over ``extract_with_telemetry`` for callers that don't
        need the refusals/source metadata.
        """
        return self.extract_with_telemetry(text, observations).proposal

    def extract_with_telemetry(
        self,
        text: str,
        observations: list[Observation],
    ) -> VitalsExtractionResult:
        """Same extraction as ``extract_with_observations``, with audit metadata.

        Returns the proposal plus:
        - ``refusals``: fields the parser dropped during validation (out of
          range, ambiguous unit, atomic BP partial). Used by
          ``post_generate_summary`` to emit ``VITALS_FIELD_REFUSED``.
        - ``source``: which path(s) contributed surviving fields to the
          FINAL proposal — ``observations``, ``regex``, ``both``, or
          ``none``. Classifying off the final survivors (rather than raw
          extraction) prevents the race the risk-hunter flagged: a
          fully-refused Nabla BP-panel used to land as ``observations`` in
          telemetry even though no observation data survived validation.

        ``display`` is rebuilt from the validated ``data`` dict via
        ``_format_vitals_display`` rather than echoed from ``text``. Echoing
        the source text led to a prod failure where a refused field (e.g.
        BP 38/22 — systole below the floor) was dropped from ``data`` but
        still appeared in ``display``, so the clinician approved a value
        that didn't make it into the chart. The display now describes only
        what will actually be inserted.
        """
        refusals: list[_Refusal] = []
        obs_data = _parse_observations(observations, refusals=refusals)
        regex_data = _parse_vitals(text, refusals=refusals)
        data: dict[str, int | float | None] = dict(regex_data)
        for field, value in obs_data.items():
            if value is not None:
                data[field] = value
        # Atomic BP pair: if either side is refused, drop both. A half-BP is
        # clinically meaningless and pollutes downstream FHIR/analytics
        # consumers even when the vitals UI hides it (the row formatter only
        # renders BP when both sides are present, but ``data`` is what
        # ``/insert-commands`` writes and what downstream consumers read).
        # "Half-written BP is worse than a clean drop." Applied after both
        # sources merge so split-component observations (8480-6 + 8462-4 as
        # separate Observations) also benefit.
        sys_present = data.get("blood_pressure_systole") is not None
        dia_present = data.get("blood_pressure_diastole") is not None
        if sys_present != dia_present:
            # Record the side that survived its own per-field gate but is
            # being dropped by the atomic-pair rule (the other side was
            # already recorded as ``out_of_range`` inside _validate_field).
            orphan_field = "blood_pressure_systole" if sys_present else "blood_pressure_diastole"
            _record_refusal(refusals, orphan_field, REFUSAL_REASON_ATOMIC_BP_PARTIAL)
            data.pop("blood_pressure_systole", None)
            data.pop("blood_pressure_diastole", None)
        # Source classification: based on the FINAL surviving fields, not
        # the raw extraction. obs_data / regex_data still hold the
        # pre-merge, pre-atomic-sweep snapshots; intersect them against
        # data to determine which side actually contributed.
        surviving_fields = {field for field, value in data.items() if value is not None}
        obs_contributed = bool(surviving_fields & set(obs_data.keys()))
        regex_contributed = bool(surviving_fields & set(regex_data.keys()))
        if obs_contributed and regex_contributed:
            source = "both"
        elif obs_contributed:
            source = "observations"
        elif regex_contributed:
            source = "regex"
        else:
            source = "none"
        if not data:
            return VitalsExtractionResult(proposal=None, refusals=refusals, source=source)
        proposal = CommandProposal(
            command_type=self.command_type,
            display=_format_vitals_display(data),
            data=data,
        )
        return VitalsExtractionResult(proposal=proposal, refusals=refusals, source=source)

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        bp_site_raw = data.get("blood_pressure_position_and_site")
        bp_site = VitalsCommand.BloodPressureSite(bp_site_raw) if bp_site_raw is not None else None
        return VitalsCommand(
            height=data.get("height"),
            weight_lbs=data.get("weight_lbs"),
            body_temperature=data.get("body_temperature"),
            blood_pressure_systole=data.get("blood_pressure_systole"),
            blood_pressure_diastole=data.get("blood_pressure_diastole"),
            pulse=data.get("pulse"),
            respiration_rate=data.get("respiration_rate"),
            oxygen_saturation=data.get("oxygen_saturation"),
            blood_pressure_position_and_site=bp_site,
            note=data.get("note"),
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
