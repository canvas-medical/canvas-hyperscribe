from unittest.mock import MagicMock, patch

import pytest

from hyperscribe.scribe.backend.models import CodingEntry, Observation
from hyperscribe.scribe.commands.vitals import (
    REFUSAL_REASON_AMBIGUOUS_UNIT,
    REFUSAL_REASON_ATOMIC_BP_PARTIAL,
    REFUSAL_REASON_OUT_OF_RANGE,
    VitalsParser,
    _format_vitals_display,
    _parse_observations,
    _parse_vitals,
)


def test_extract_basic() -> None:
    """Compact format (the format the original regex parser handled correctly).

    ``display`` is rebuilt from validated ``data`` rather than echoed from input,
    so the format matches the post-edit formatter in static/summary.js (no flash).
    """
    parser = VitalsParser()
    proposal = parser.extract("BP 120/80, HR 72, RR 16, SpO2 98%")
    assert proposal is not None
    assert proposal.command_type == "vitals"
    assert proposal.data["blood_pressure_systole"] == 120
    assert proposal.data["blood_pressure_diastole"] == 80
    assert proposal.data["pulse"] == 72
    assert proposal.data["respiration_rate"] == 16
    assert proposal.data["oxygen_saturation"] == 98
    assert proposal.display == "BP 120/80 mmHg, HR 72 bpm, RR 16 /min, SpO2 98%"
    assert proposal.selected is True


def test_extract_no_parseable_returns_none() -> None:
    """Free-text with no recognisable vitals must not produce a proposal."""
    parser = VitalsParser()
    assert parser.extract("Patient appears well.") is None


def test_parse_vitals_blood_pressure() -> None:
    """Whitespace around the BP slash must not block parsing."""
    result = _parse_vitals("BP 130 / 85")
    assert result["blood_pressure_systole"] == 130
    assert result["blood_pressure_diastole"] == 85


def test_parse_vitals_all_fields() -> None:
    """Sanity-check every field on a multi-line compact-format vitals string."""
    text = "BP 120/80\nHR 72\nRR 16\nSpO2 98\nTemperature: 98.6\nHeight: 5'10\"\nWeight: 180 lbs"
    result = _parse_vitals(text)
    assert result["blood_pressure_systole"] == 120
    assert result["blood_pressure_diastole"] == 80
    assert result["pulse"] == 72
    assert result["respiration_rate"] == 16
    assert result["oxygen_saturation"] == 98
    assert result["body_temperature"] == 98.6
    assert result["height"] == 70  # 5*12 + 10
    assert result["weight_lbs"] == 180


def test_parse_vitals_empty() -> None:
    """Non-vitals prose must produce an empty result without raising."""
    assert _parse_vitals("Patient appears well.") == {}


# --- Verbose markdown-bullet failure modes -----------------------------------------
# The regex parser previously dropped SpO2/RR (and metric height/weight) on Nabla's
# verbose markdown-bullet format. These tests pin the four failure modes.


def test_parse_vitals_verbose_markdown_bullet_format() -> None:
    """Reproduce the prod failure on Nabla's verbose markdown bullet format — every field must populate."""
    text = (
        "* Blood pressure: 103/56 mmHg (right arm cuff), repeat 106/56 mmHg\n"
        "* Heart rate: 74 bpm\n"
        "* Respiratory rate: 16 breaths per minute\n"
        "* Temperature: 97.8 °F\n"
        "* O2 saturation: 94%"
    )
    result = _parse_vitals(text)
    assert result["blood_pressure_systole"] == 103
    assert result["blood_pressure_diastole"] == 56
    assert result["pulse"] == 74
    assert result["respiration_rate"] == 16
    assert result["body_temperature"] == 97.8
    assert result["oxygen_saturation"] == 94


def test_parse_vitals_o2_saturation_phrasings() -> None:
    """``O2 saturation``, ``SpO2``, ``Oxygen saturation`` all populate ``oxygen_saturation``."""
    assert _parse_vitals("O2 saturation: 97%")["oxygen_saturation"] == 97
    assert _parse_vitals("SpO2 95%")["oxygen_saturation"] == 95
    assert _parse_vitals("Oxygen saturation: 94%")["oxygen_saturation"] == 94
    assert _parse_vitals("O2 sat 96%")["oxygen_saturation"] == 96
    assert _parse_vitals("SpO2: 98")["oxygen_saturation"] == 98


def test_parse_vitals_respiratory_rate_phrasings() -> None:
    """``Respiratory rate``, ``Respiration rate``, ``Resp rate``, ``RR`` all populate ``respiration_rate``."""
    assert _parse_vitals("Respiratory rate: 16 breaths per minute")["respiration_rate"] == 16
    assert _parse_vitals("Respiration rate: 18")["respiration_rate"] == 18
    assert _parse_vitals("Resp rate: 14")["respiration_rate"] == 14
    assert _parse_vitals("RR 18 /min")["respiration_rate"] == 18


def test_parse_vitals_temperature_celsius_converts_to_fahrenheit() -> None:
    """Celsius input must be converted to Fahrenheit (VitalsCommand expects °F)."""
    # 37.0°C == 98.6°F.
    result = _parse_vitals("Temperature: 37.0 °C")
    assert result["body_temperature"] == 98.6


def test_parse_vitals_height_metric_converts_to_inches() -> None:
    """``Height: 170 cm`` becomes 67 inches (170 * 0.393701 = 66.93 → 67)."""
    result = _parse_vitals("Height: 170 cm")
    assert result["height"] == 67


def test_parse_vitals_weight_metric_converts_to_lbs() -> None:
    """``Weight: 75 kg`` becomes 165 lbs (75 * 2.20462 = 165.35 → 165)."""
    result = _parse_vitals("Weight: 75 kg")
    assert result["weight_lbs"] == 165


# --- Observation-driven parsing (Path A) -------------------------------------------


def _loinc_obs(code: str, value: str, *, unit: str = "", display: str = "") -> Observation:
    """Build an Observation whose only coding entry is a LOINC code."""
    return Observation(
        display=display or code,
        value=value,
        unit=unit,
        coding=[CodingEntry(system="LOINC", code=code, display=display)],
    )


def test_parse_observations_empty() -> None:
    """Empty observation list produces an empty dict, never raises."""
    assert _parse_observations([]) == {}


def test_parse_observations_bp_panel() -> None:
    """LOINC 85354-9 (BP panel) value ``"103/56"`` splits into systole + diastole."""
    obs = [_loinc_obs("85354-9", "103/56", unit="mmHg", display="Blood pressure")]
    result = _parse_observations(obs)
    assert result["blood_pressure_systole"] == 103
    assert result["blood_pressure_diastole"] == 56


def test_parse_observations_bp_split_components() -> None:
    """Nabla may emit systole (8480-6) and diastole (8462-4) as separate observations."""
    obs = [
        _loinc_obs("8480-6", "103", unit="mmHg", display="Systolic BP"),
        _loinc_obs("8462-4", "56", unit="mmHg", display="Diastolic BP"),
    ]
    result = _parse_observations(obs)
    assert result["blood_pressure_systole"] == 103
    assert result["blood_pressure_diastole"] == 56


def test_parse_observations_full_panel() -> None:
    """All six core vital signs map through their LOINC codes with US-customary units."""
    obs = [
        _loinc_obs("8867-4", "74", unit="bpm", display="Heart rate"),
        _loinc_obs("9279-1", "16", unit="/min", display="Respiratory rate"),
        _loinc_obs("2708-6", "94", unit="%", display="Oxygen saturation"),
        _loinc_obs("8310-5", "97.8", unit="°F", display="Body temperature"),
        _loinc_obs("85354-9", "103/56", unit="mmHg", display="Blood pressure"),
    ]
    result = _parse_observations(obs)
    assert result == {
        "pulse": 74,
        "respiration_rate": 16,
        "oxygen_saturation": 94,
        "body_temperature": 97.8,
        "blood_pressure_systole": 103,
        "blood_pressure_diastole": 56,
    }


def test_parse_observations_temperature_celsius() -> None:
    """Celsius observations are converted to Fahrenheit."""
    obs = [_loinc_obs("8310-5", "37.0", unit="°C", display="Body temperature")]
    result = _parse_observations(obs)
    assert result["body_temperature"] == 98.6


def test_parse_observations_weight_kg() -> None:
    """Weight in kg converts to lbs."""
    obs = [_loinc_obs("29463-7", "75", unit="kg", display="Body weight")]
    result = _parse_observations(obs)
    assert result["weight_lbs"] == 165


def test_parse_observations_height_cm() -> None:
    """Height in cm converts to inches."""
    obs = [_loinc_obs("8302-2", "170", unit="cm", display="Body height")]
    result = _parse_observations(obs)
    assert result["height"] == 67


def test_parse_observations_pulse_ox_via_alternate_loinc() -> None:
    """LOINC 59408-5 (SpO2 via pulse oximetry) populates oxygen_saturation too."""
    obs = [_loinc_obs("59408-5", "95", unit="%", display="SpO2")]
    result = _parse_observations(obs)
    assert result["oxygen_saturation"] == 95


def test_parse_observations_unknown_loinc_ignored() -> None:
    """An observation with a LOINC code we don't map is silently dropped."""
    obs = [_loinc_obs("99999-9", "42", unit="x", display="Mystery")]
    assert _parse_observations(obs) == {}


def test_parse_observations_non_loinc_system_still_works() -> None:
    """We match by code, not system, so non-LOINC ``system`` strings still resolve."""
    obs = [
        Observation(
            display="Heart rate",
            value="74",
            unit="bpm",
            coding=[CodingEntry(system="", code="8867-4", display="")],
        )
    ]
    result = _parse_observations(obs)
    assert result["pulse"] == 74


def test_parse_observations_value_with_units_appended_parsed() -> None:
    """Nabla sometimes returns the unit inside the value string — we extract the leading number."""
    obs = [_loinc_obs("8867-4", "74 bpm", display="Heart rate")]
    result = _parse_observations(obs)
    assert result["pulse"] == 74


# --- VitalsParser.extract_with_observations ----------------------------------------


def test_extract_with_observations_prefers_observations_over_regex() -> None:
    """When both sources supply pulse, the observation value wins."""
    parser = VitalsParser()
    obs = [_loinc_obs("8867-4", "80", unit="bpm", display="Heart rate")]
    proposal = parser.extract_with_observations("HR 72", obs)
    assert proposal is not None
    assert proposal.data["pulse"] == 80  # observation wins


def test_extract_with_observations_regex_fills_gaps() -> None:
    """Observations supply BP, the regex picks up SpO2 from the free text."""
    parser = VitalsParser()
    obs = [_loinc_obs("85354-9", "120/80", unit="mmHg", display="Blood pressure")]
    proposal = parser.extract_with_observations("SpO2 95%", obs)
    assert proposal is not None
    assert proposal.data["blood_pressure_systole"] == 120
    assert proposal.data["blood_pressure_diastole"] == 80
    assert proposal.data["oxygen_saturation"] == 95


def test_extract_with_observations_empty_text_with_observations() -> None:
    """Observation-only path: emit a proposal even when the vitals section is empty.

    ``display`` is rebuilt from validated data, not echoed from the (empty) text,
    so the clinician sees the observation-sourced values immediately.
    """
    parser = VitalsParser()
    obs = [_loinc_obs("8867-4", "74", unit="bpm", display="Heart rate")]
    proposal = parser.extract_with_observations("", obs)
    assert proposal is not None
    assert proposal.data["pulse"] == 74
    assert proposal.display == "HR 74 bpm"


def test_extract_with_observations_none_returns_none() -> None:
    """No regex hits and no observations means no proposal."""
    parser = VitalsParser()
    assert parser.extract_with_observations("Patient appears well.", []) is None


def test_extract_with_observations_full_verbose_panel() -> None:
    """End-to-end: the verbose-format prod failure expressed as LOINC observations (Path A)."""
    parser = VitalsParser()
    obs = [
        _loinc_obs("85354-9", "103/56", unit="mmHg", display="Blood pressure"),
        _loinc_obs("8867-4", "74", unit="bpm", display="Heart rate"),
        _loinc_obs("9279-1", "16", unit="/min", display="Respiratory rate"),
        _loinc_obs("8310-5", "97.8", unit="°F", display="Body temperature"),
        _loinc_obs("2708-6", "94", unit="%", display="Oxygen saturation"),
    ]
    proposal = parser.extract_with_observations("", obs)
    assert proposal is not None
    assert proposal.data == {
        "blood_pressure_systole": 103,
        "blood_pressure_diastole": 56,
        "pulse": 74,
        "respiration_rate": 16,
        "body_temperature": 97.8,
        "oxygen_saturation": 94,
    }


# --- Negative regression tests -----------------------------------------------------
# These pin failure modes the prior implementation silently mis-handled:
#  * SpO2 regex used to capture O2 flow rate (e.g., "O2 2L NC" -> sat=2).
#  * Parenthetical "Oxygen saturation (SpO2): 98%" used to miss.
#  * Temperature with unknown unit (Kelvin, empty) used to be assumed °F.
#  * Impossible values (BP 999/999, pulse 9999, SpO2 200%) used to flow through.


def test_parse_vitals_does_not_extract_spo2_from_flow_rate() -> None:
    """Flow-rate phrasings like ``O2 2L NC`` must NOT populate ``oxygen_saturation``."""
    for text in (
        "O2 2L NC",
        "On O2 at 3 liters",
        "Oxygen therapy at 2L",
        "Patient on O2 via NC at 4 LPM",
    ):
        result = _parse_vitals(text)
        assert "oxygen_saturation" not in result, f"flow-rate leaked into SpO2 for {text!r}: {result}"


def test_parse_vitals_extracts_spo2_from_parenthetical_form() -> None:
    """Nabla's verbose ``Oxygen saturation (SpO2): 98%`` form must populate ``oxygen_saturation``."""
    result = _parse_vitals("- Oxygen saturation (SpO2): 98%")
    assert result["oxygen_saturation"] == 98


def test_observation_temperature_unknown_unit_refused_when_out_of_range() -> None:
    """Kelvin temperatures must be refused (not silently written as °F)."""
    obs = [_loinc_obs("8310-5", "310", unit="K", display="Body temperature")]
    result = _parse_observations(obs)
    assert "body_temperature" not in result


def test_observation_temperature_empty_unit_inferred_celsius_via_range_gate() -> None:
    """An observation value in the °C range with no unit converts to °F via the plausibility gate."""
    obs = [_loinc_obs("8310-5", "37", unit="", display="Body temperature")]
    result = _parse_observations(obs)
    # 37°C -> 98.6°F.
    assert result["body_temperature"] == 98.6


def test_observation_temperature_empty_unit_already_fahrenheit_passes_through() -> None:
    """An observation value already in the °F range with no unit passes through unconverted."""
    obs = [_loinc_obs("8310-5", "98.6", unit="", display="Body temperature")]
    result = _parse_observations(obs)
    assert result["body_temperature"] == 98.6


def test_observation_values_out_of_range_refused() -> None:
    """Impossible values (BP 999/999, pulse 9999, SpO2 200) must NOT be written."""
    obs = [
        _loinc_obs("85354-9", "999/999", unit="mmHg", display="Blood pressure"),
        _loinc_obs("8867-4", "9999", unit="bpm", display="Heart rate"),
        _loinc_obs("2708-6", "200", unit="%", display="Oxygen saturation"),
        _loinc_obs("9279-1", "999", unit="/min", display="Respiratory rate"),
    ]
    result = _parse_observations(obs)
    assert "blood_pressure_systole" not in result
    assert "blood_pressure_diastole" not in result
    assert "pulse" not in result
    assert "oxygen_saturation" not in result
    assert "respiration_rate" not in result


def test_regex_path_values_out_of_range_refused() -> None:
    """The regex (fallback) path must apply the same plausibility gate as the observation path."""
    text = "BP 999/999\nHR 9999\nSpO2 200%\nRR 999"
    result = _parse_vitals(text)
    assert "blood_pressure_systole" not in result
    assert "blood_pressure_diastole" not in result
    assert "pulse" not in result
    assert "oxygen_saturation" not in result
    assert "respiration_rate" not in result


def test_observation_weight_empty_unit_in_ambiguous_band_refused() -> None:
    """Empty-unit weight inside the kg/lbs overlap band (30-250) must be refused.

    70 could be 70 kg (~155 lbs) or 70 lbs (~32 kg child). Without an
    explicit unit we cannot tell, so we refuse rather than silently corrupt
    the chart.
    """
    obs = [_loinc_obs("29463-7", "70", unit="", display="Body weight")]
    result = _parse_observations(obs)
    assert "weight_lbs" not in result


def test_observation_weight_empty_unit_clearly_lbs_accepted() -> None:
    """Empty-unit weight above the ambiguity band is unambiguously lbs and accepted."""
    obs = [_loinc_obs("29463-7", "280", unit="", display="Body weight")]
    result = _parse_observations(obs)
    # 280 lbs is plausible for an adult; no adult is 280 kg (=617 lbs).
    assert result["weight_lbs"] == 280


def test_observation_weight_explicit_kg_converts_correctly() -> None:
    """An explicit kg unit still converts even when the magnitude could be ambiguous."""
    obs = [_loinc_obs("29463-7", "75", unit="kg", display="Body weight")]
    result = _parse_observations(obs)
    # 75 kg → 165 lbs (75 * 2.20462 = 165.35 → 165).
    assert result["weight_lbs"] == 165


def test_observation_height_empty_unit_in_ambiguous_band_refused() -> None:
    """Empty-unit height inside the cm/in overlap band (30-80) must be refused.

    65 could be 65 inches (5'5") or 65 cm (infant). Without an explicit
    unit we cannot tell, so we refuse rather than silently corrupt the chart.
    """
    obs = [_loinc_obs("8302-2", "65", unit="", display="Body height")]
    result = _parse_observations(obs)
    assert "height" not in result


def test_observation_height_empty_unit_clearly_inches_accepted() -> None:
    """Empty-unit height above the ambiguity band is unambiguously inches and accepted."""
    obs = [_loinc_obs("8302-2", "84", unit="", display="Body height")]
    result = _parse_observations(obs)
    # 84 inches = 7 feet — plausible upper-edge adult height. 84 cm would
    # be a 2-year-old, far below the cm window for an adult patient.
    assert result["height"] == 84


def test_observation_loinc_iteration_is_deterministic() -> None:
    """An observation carrying multiple mapped LOINC codes must resolve via the declared priority order."""
    # Pulse + RR codes attached to the same observation. Declared order in
    # ``_LOINC_TO_FIELD`` is pulse (8867-4) before RR (9279-1), so the
    # observation maps to pulse first; RR stays open for a later observation.
    # Value 40 is plausible for BOTH pulse (≥30) and RR (≤60), letting us
    # verify the loop doesn't early-return without picking a value that the
    # range gate would refuse for either field.
    obs = [
        Observation(
            display="Multi-code",
            value="40",
            unit="bpm",
            coding=[
                CodingEntry(system="LOINC", code="9279-1", display=""),
                CodingEntry(system="LOINC", code="8867-4", display=""),
            ],
        ),
    ]
    result = _parse_observations(obs)
    # Pulse wins because it appears earlier in _LOINC_TO_FIELD priority order.
    assert result.get("pulse") == 40
    # RR also gets written because the loop no longer early-returns after
    # the first match — this is intentional: subsequent codes on the same
    # observation get a chance to populate their field.
    assert result.get("respiration_rate") == 40


def test_build() -> None:
    parser = VitalsParser()
    data = {
        "blood_pressure_systole": 120,
        "blood_pressure_diastole": 80,
        "pulse": 72,
        "respiration_rate": 16,
        "oxygen_saturation": 98,
        "blood_pressure_position_and_site": 1,
        "note": "Patient was anxious",
    }
    with patch("hyperscribe.scribe.commands.vitals.VitalsCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-789", "cmd-uuid")

    mock_cmd.BloodPressureSite.assert_called_once_with(1)
    mock_cmd.assert_called_once_with(
        height=None,
        weight_lbs=None,
        body_temperature=None,
        blood_pressure_systole=120,
        blood_pressure_diastole=80,
        pulse=72,
        respiration_rate=16,
        oxygen_saturation=98,
        blood_pressure_position_and_site=mock_cmd.BloodPressureSite.return_value,
        note="Patient was anxious",
        note_uuid="note-uuid-789",
        command_uuid="cmd-uuid",
    )


def test_parse_vitals_respiratory_rate_phrasing() -> None:
    # Nabla/LLM emits "Respiratory rate", not "Respiration" — the old regex missed it.
    assert _parse_vitals("Respiratory rate: 14 breaths/min")["respiration_rate"] == 14


def test_parse_vitals_height_plain_inches() -> None:
    # The LLM normalizes spoken height to plain inches ("70 in"), never the 5'10" form.
    assert _parse_vitals("Height: 70 in")["height"] == 70
    assert _parse_vitals("Height: 70 inches")["height"] == 70


def test_parse_vitals_height_spoken_feet_inches() -> None:
    assert _parse_vitals("Height: 5 ft 10 in")["height"] == 70
    assert _parse_vitals("Height: 5 feet 10 inches")["height"] == 70
    assert _parse_vitals("Height: 5 foot 10")["height"] == 70


def test_parse_vitals_height_feet_only() -> None:
    assert _parse_vitals("Height: 6 feet")["height"] == 72


def test_parse_vitals_production_display_string() -> None:
    # The exact multi-line display the Scribe pipeline produced on scribeqa-sandbox.
    text = (
        "- Blood pressure: 124/76 mmHg\n"
        "- Heart rate: 72 bpm\n"
        "- Respiratory rate: 14 breaths/min\n"
        "- Temperature: 98.2 °F\n"
        "- Oxygen saturation: 99%\n"
        "- Weight: 195 lb\n"
        "- Height: 70 in"
    )
    result = _parse_vitals(text)
    assert result["blood_pressure_systole"] == 124
    assert result["blood_pressure_diastole"] == 76
    assert result["pulse"] == 72
    assert result["respiration_rate"] == 14
    assert result["body_temperature"] == 98.2
    assert result["oxygen_saturation"] == 99
    assert result["weight_lbs"] == 195
    assert result["height"] == 70


def test_build_without_new_fields() -> None:
    parser = VitalsParser()
    data = {
        "blood_pressure_systole": 120,
        "blood_pressure_diastole": 80,
        "pulse": 72,
    }
    with patch("hyperscribe.scribe.commands.vitals.VitalsCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        height=None,
        weight_lbs=None,
        body_temperature=None,
        blood_pressure_systole=120,
        blood_pressure_diastole=80,
        pulse=72,
        respiration_rate=None,
        oxygen_saturation=None,
        blood_pressure_position_and_site=None,
        note=None,
        note_uuid="note-uuid",
        command_uuid="cmd-uuid",
    )


# --- Display/data agreement invariant (UAT Finding 1) ------------------------------
# The display string must describe ONLY fields present in ``data``. If a field is
# refused by ``_validate_field`` (range gate) it must be absent from BOTH ``data``
# and ``display``. Prod failure mode: hypotension "BP 38/22" → systole below floor →
# dropped from data, but Nabla's raw text still shown → clinician approves a
# half-written BP. Fix: rebuild display from validated data.


def test_format_vitals_display_empty_data_is_empty_string() -> None:
    """Empty data dict yields an empty display string."""
    assert _format_vitals_display({}) == ""


def test_format_vitals_display_full_panel() -> None:
    """Canonical order matches the post-edit formatter in static/summary.js."""
    data: dict[str, int | float | None] = {
        "blood_pressure_systole": 120,
        "blood_pressure_diastole": 80,
        "pulse": 72,
        "respiration_rate": 16,
        "oxygen_saturation": 98,
        "body_temperature": 98.6,
        "height": 70,
        "weight_lbs": 180,
    }
    assert _format_vitals_display(data) == (
        "BP 120/80 mmHg, HR 72 bpm, RR 16 /min, SpO2 98%, Temp 98.6 °F, Height 70 in, Weight 180 lbs"
    )


def test_format_vitals_display_partial_bp_drops_pair() -> None:
    """BP pair: when only one of systole/diastole is present, neither appears."""
    # Diastole present, systole absent (the hypotension UAT case): no BP in display.
    assert _format_vitals_display({"blood_pressure_diastole": 22}) == ""
    # Systole present, diastole absent: also no BP in display.
    assert _format_vitals_display({"blood_pressure_systole": 38}) == ""


def test_extract_hypotension_refused_systole_drops_atomic_bp_pair() -> None:
    """UAT Finding 1 (hypotension): refused systole drops BOTH sides of the BP pair.

    Real transcript shape: "Blood pressure 25 over 22, HR 110, RR 28, SpO2 88 on 4L, Temp 95.8".
    Systole 25 < 30 SDK floor → refused. Diastole 22 ≥ 20 → would survive the per-field gate,
    but BP is atomic: a half-BP is clinically meaningless and pollutes downstream
    consumers (FHIR exports, analytics) even when the vitals UI hides a half-pair.
    Both sides must be absent from data AND display.
    """
    text = "BP 25/22, HR 110, RR 28, SpO2 88, Temp 95.8"
    parser = VitalsParser()
    proposal = parser.extract_with_observations(text, [])
    assert proposal is not None
    assert "blood_pressure_systole" not in proposal.data
    assert "blood_pressure_diastole" not in proposal.data
    assert "25/22" not in proposal.display
    assert "BP" not in proposal.display
    # The other vitals still appear and are in the canonical format.
    assert proposal.display == "HR 110 bpm, RR 28 /min, SpO2 88%, Temp 95.8 °F"


def test_extract_isolated_diastole_observation_drops_atomic_bp_pair() -> None:
    """Split-component path: an isolated diastole observation must not produce a half-BP.

    Nabla sometimes emits systole and diastole as separate LOINC observations (8480-6
    and 8462-4). If only one survives — whether refused by the range gate or simply
    absent from Nabla's payload — the atomic-pair contract drops the orphan rather
    than letting a half-BP leak into the chart.
    """
    parser = VitalsParser()
    obs = [
        # Diastole alone (valid value), no companion systole observation.
        _loinc_obs("8462-4", "80", unit="mmHg", display="Diastolic BP"),
        # An accompanying valid pulse so the proposal isn't empty.
        _loinc_obs("8867-4", "72", unit="bpm", display="Heart rate"),
    ]
    proposal = parser.extract_with_observations("", obs)
    assert proposal is not None
    assert "blood_pressure_systole" not in proposal.data
    assert "blood_pressure_diastole" not in proposal.data
    assert proposal.data["pulse"] == 72
    assert "BP" not in proposal.display
    assert proposal.display == "HR 72 bpm"


def test_extract_severe_hypoxia_refused_spo2_not_in_display() -> None:
    """UAT Finding 1 (hypoxia): refused SpO2 (30 < 60 floor) must not appear in display.

    Real transcript: "SpO2 30 percent on room air"-style input. With the tightened
    SpO2 floor at 60 (UI form rejects <60), 30% is refused and must disappear from
    BOTH data and display.
    """
    text = "HR 130, RR 35, SpO2 30%, Temp 99.8, BP 90/60"
    parser = VitalsParser()
    proposal = parser.extract_with_observations(text, [])
    assert proposal is not None
    assert "oxygen_saturation" not in proposal.data
    assert "SpO2" not in proposal.display
    assert "30%" not in proposal.display
    # The fields that survived are present.
    assert proposal.data["pulse"] == 130
    assert proposal.data["respiration_rate"] == 35
    assert proposal.data["body_temperature"] == 99.8
    assert proposal.data["blood_pressure_systole"] == 90
    assert proposal.data["blood_pressure_diastole"] == 60


def test_extract_display_matches_data_invariant_via_observations() -> None:
    """Same invariant on the observation path: refused values must not appear in display."""
    parser = VitalsParser()
    obs = [
        # Systole 25 → refused (below SDK floor of 30).
        _loinc_obs("8480-6", "25", unit="mmHg", display="Systolic BP"),
        # Diastole 22 → accepted (≥ 20 SDK floor).
        _loinc_obs("8462-4", "22", unit="mmHg", display="Diastolic BP"),
        # SpO2 30 → refused (below 60 floor).
        _loinc_obs("2708-6", "30", unit="%", display="Oxygen saturation"),
        # Pulse 110 → accepted.
        _loinc_obs("8867-4", "110", unit="bpm", display="Heart rate"),
    ]
    proposal = parser.extract_with_observations("", obs)
    assert proposal is not None
    assert "blood_pressure_systole" not in proposal.data
    assert "oxygen_saturation" not in proposal.data
    # Refused fields never appear in display.
    assert "25" not in proposal.display
    assert "30%" not in proposal.display
    assert "SpO2" not in proposal.display
    # Survivors do appear.
    assert proposal.display == "HR 110 bpm"


# --- _FIELD_RANGES boundary tests (UAT Finding 2) ----------------------------------
# Each new boundary value must be refused. Documents the intersection of parser, SDK
# pydantic constraints, and UI vitals-row.js spinbutton bounds.


@pytest.mark.parametrize(
    ("text", "field"),
    [
        # pulse: floor raised from 20 → 30 (SDK + UI agree).
        ("HR 25", "pulse"),
        # respiration_rate: floor raised from 4 → 6, ceiling lowered from 80 → 60.
        ("RR 5", "respiration_rate"),
        ("RR 75", "respiration_rate"),
        # oxygen_saturation: floor raised from 40 → 60 (UI rejects <60).
        ("SpO2 50%", "oxygen_saturation"),
        # body_temperature: floor raised from 80 → 85, ceiling lowered from 115 → 107.
        ("Temp 84", "body_temperature"),
        ("Temp 110", "body_temperature"),
    ],
)
def test_regex_path_rejects_value_below_new_boundary(text: str, field: str) -> None:
    """Each value lies between the OLD parser bound and the NEW (tighter) bound — must be refused now."""
    result = _parse_vitals(text)
    assert field not in result, f"{text!r} should refuse {field}, got {result}"


def test_regex_path_rejects_bp_diastole_above_new_ceiling() -> None:
    """Diastole ceiling lowered from 200 → 180 (SDK + UI). 195 was accepted before; refused now.

    ``_parse_vitals`` writes per-field; the atomic BP-pair sweep lives in
    ``extract_with_observations`` (one chokepoint covering all paths), so this
    direct-regex test only asserts the diastole side.
    """
    result = _parse_vitals("BP 140/195")
    assert "blood_pressure_diastole" not in result


def test_observation_path_rejects_pulse_below_30_floor() -> None:
    """Pulse 25 was accepted by the old parser (floor=20) but rejected by SDK pydantic (ge=30)."""
    obs = [_loinc_obs("8867-4", "25", unit="bpm", display="Heart rate")]
    assert "pulse" not in _parse_observations(obs)


def test_observation_path_rejects_spo2_below_60_floor() -> None:
    """SpO2 50 was accepted by the old parser (floor=40) but rejected by the UI form (min=60)."""
    obs = [_loinc_obs("2708-6", "50", unit="%", display="Oxygen saturation")]
    assert "oxygen_saturation" not in _parse_observations(obs)


def test_observation_path_rejects_temp_above_107_ceiling() -> None:
    """Temperature 110°F was accepted by the old parser (ceiling=115) but rejected by SDK + UI (le=107)."""
    obs = [_loinc_obs("8310-5", "110", unit="°F", display="Body temperature")]
    assert "body_temperature" not in _parse_observations(obs)


def test_observation_path_rejects_temp_below_85_floor() -> None:
    """Temperature 80°F was accepted by the old parser (floor=80) but rejected by SDK + UI (ge=85)."""
    obs = [_loinc_obs("8310-5", "80", unit="°F", display="Body temperature")]
    assert "body_temperature" not in _parse_observations(obs)


def test_observation_path_rejects_rr_above_60_ceiling() -> None:
    """RR 75 was accepted by the old parser (ceiling=80) but rejected by SDK + UI (le=60)."""
    obs = [_loinc_obs("9279-1", "75", unit="/min", display="Respiratory rate")]
    assert "respiration_rate" not in _parse_observations(obs)


def test_observation_path_rejects_diastole_above_180_ceiling() -> None:
    """Diastole 195 was accepted by the old parser (ceiling=200) but rejected by SDK + UI (le=180)."""
    obs = [_loinc_obs("8462-4", "195", unit="mmHg", display="Diastolic BP")]
    assert "blood_pressure_diastole" not in _parse_observations(obs)


def test_observation_path_accepts_new_lower_boundaries() -> None:
    """Sanity: values AT the new floors must still be accepted."""
    obs = [
        _loinc_obs("8867-4", "30", unit="bpm", display="Heart rate"),
        _loinc_obs("9279-1", "6", unit="/min", display="Respiratory rate"),
        _loinc_obs("2708-6", "60", unit="%", display="Oxygen saturation"),
        _loinc_obs("8310-5", "85", unit="°F", display="Body temperature"),
        _loinc_obs("8462-4", "180", unit="mmHg", display="Diastolic BP"),
    ]
    result = _parse_observations(obs)
    assert result["pulse"] == 30
    assert result["respiration_rate"] == 6
    assert result["oxygen_saturation"] == 60
    assert result["body_temperature"] == 85
    assert result["blood_pressure_diastole"] == 180


def test_observation_path_accepts_new_upper_boundaries() -> None:
    """Sanity: values AT the new ceilings must still be accepted."""
    obs = [
        _loinc_obs("8867-4", "250", unit="bpm", display="Heart rate"),
        _loinc_obs("9279-1", "60", unit="/min", display="Respiratory rate"),
        _loinc_obs("2708-6", "100", unit="%", display="Oxygen saturation"),
        _loinc_obs("8310-5", "107", unit="°F", display="Body temperature"),
        _loinc_obs("8462-4", "20", unit="mmHg", display="Diastolic BP"),
    ]
    result = _parse_observations(obs)
    assert result["pulse"] == 250
    assert result["respiration_rate"] == 60
    assert result["oxygen_saturation"] == 100
    assert result["body_temperature"] == 107
    assert result["blood_pressure_diastole"] == 20


# --- SDK-canonical _FIELD_RANGES (Fix 3) ----------------------------------------------
# After widening the parser bounds to match SDK pydantic constraints exactly, values
# that were previously refused by the parser-but-accepted-by-SDK must now flow through.


def test_observation_path_accepts_severe_shock_systole_at_sdk_floor() -> None:
    """Systole 30 (SDK floor) is now accepted by the parser too.

    Previously refused: parser floor was 40, so severe-shock systole 30-39
    landed as a half-BP candidate (atomic sweep then dropped both sides).
    With the parser matching SDK pydantic ge=30, value 30 flows through.
    """
    obs = [
        _loinc_obs("8480-6", "30", unit="mmHg", display="Systolic BP"),
        _loinc_obs("8462-4", "20", unit="mmHg", display="Diastolic BP"),
    ]
    result = _parse_observations(obs)
    assert result["blood_pressure_systole"] == 30
    assert result["blood_pressure_diastole"] == 20


def test_observation_path_accepts_super_bariatric_weight_at_sdk_ceiling() -> None:
    """Weight 1500 lbs (SDK ceiling) is now accepted; previously refused at parser ceiling 1000."""
    obs = [_loinc_obs("29463-7", "1500", unit="lbs", display="Body weight")]
    result = _parse_observations(obs)
    assert result["weight_lbs"] == 1500


def test_observation_path_accepts_pediatric_height_at_sdk_floor() -> None:
    """Height 10 in (SDK floor) is now accepted; previously refused at parser floor 12."""
    obs = [_loinc_obs("8302-2", "10", unit="in", display="Body height")]
    result = _parse_observations(obs)
    assert result["height"] == 10


def test_observation_path_accepts_tall_height_at_sdk_ceiling() -> None:
    """Height 108 in (SDK ceiling) is now accepted; previously refused at parser ceiling 96."""
    obs = [_loinc_obs("8302-2", "108", unit="in", display="Body height")]
    result = _parse_observations(obs)
    assert result["height"] == 108


def test_observation_path_accepts_systole_at_sdk_ceiling() -> None:
    """Systole 305 (SDK ceiling) is now accepted; previously refused at parser ceiling 300."""
    obs = [
        _loinc_obs("8480-6", "305", unit="mmHg", display="Systolic BP"),
        _loinc_obs("8462-4", "180", unit="mmHg", display="Diastolic BP"),
    ]
    result = _parse_observations(obs)
    assert result["blood_pressure_systole"] == 305


# --- Display/data format invariant for integer-valued temperatures (Fix 1) -----------
# The JS template literal in summary.js renders ``${data.body_temperature}`` which
# after JSON round-trip turns 99.0 into 99 — so "Temp 99 °F", not "Temp 99.0 °F".
# Python's default f-string formatting of a float keeps the trailing ``.0``. Using
# ``:g`` drops it, aligning the backend with the JS rebuilder so the first edit
# doesn't flash the format.


def test_format_vitals_display_integer_valued_temperature_drops_trailing_zero() -> None:
    """Integer-valued temperature (99.0) must render as ``Temp 99 °F``, not ``Temp 99.0 °F``."""
    assert _format_vitals_display({"body_temperature": 99.0}) == "Temp 99 °F"


def test_format_vitals_display_integer_temp_matches_int_input() -> None:
    """The Python float 99.0 and the int 99 must produce the SAME display string.

    Pins the round-trip invariant: after JSON serialization, 99.0 becomes 99 in JS,
    which the frontend's template literal renders as ``99``. The backend must
    match so the display string is stable across the JSON boundary.
    """
    assert _format_vitals_display({"body_temperature": 99.0}) == _format_vitals_display({"body_temperature": 99})
    assert _format_vitals_display({"body_temperature": 99.0}) == "Temp 99 °F"


def test_format_vitals_display_decimal_temperature_preserves_precision() -> None:
    """A non-integer temperature (98.6) still renders with its decimal: ``Temp 98.6 °F``."""
    assert _format_vitals_display({"body_temperature": 98.6}) == "Temp 98.6 °F"


def test_format_vitals_display_temperatures_around_integer_boundary() -> None:
    """Various integer-valued and decimal temperatures format correctly."""
    assert _format_vitals_display({"body_temperature": 98.0}) == "Temp 98 °F"
    assert _format_vitals_display({"body_temperature": 100.0}) == "Temp 100 °F"
    assert _format_vitals_display({"body_temperature": 100.4}) == "Temp 100.4 °F"
    assert _format_vitals_display({"body_temperature": 97.8}) == "Temp 97.8 °F"


# --- extract_with_telemetry: refusals + source from FINAL surviving fields (Fix 2+4) ---


def test_extract_with_telemetry_happy_path_has_no_refusals() -> None:
    """The happy path produces no refusals. Used to pin silent-on-success behavior."""
    parser = VitalsParser()
    obs = [_loinc_obs("8867-4", "74", unit="bpm", display="Heart rate")]
    result = parser.extract_with_telemetry("BP 120/80", obs)
    assert result.proposal is not None
    assert result.refusals == []
    # Both paths contributed to the FINAL data → source is "both".
    assert result.source == "both"


def test_extract_with_telemetry_out_of_range_pulse_recorded() -> None:
    """An out-of-range pulse from regex is recorded as ``out_of_range``."""
    parser = VitalsParser()
    result = parser.extract_with_telemetry("HR 25", [])
    assert result.proposal is None
    assert [r.field for r in result.refusals] == ["pulse"]
    assert [r.reason for r in result.refusals] == [REFUSAL_REASON_OUT_OF_RANGE]
    assert result.source == "none"


def test_extract_with_telemetry_ambiguous_unit_recorded() -> None:
    """An empty-unit weight in the kg/lbs band is recorded as ``ambiguous_unit``."""
    parser = VitalsParser()
    obs = [_loinc_obs("29463-7", "70", unit="", display="Body weight")]
    result = parser.extract_with_telemetry("", obs)
    assert result.proposal is None
    assert [(r.field, r.reason) for r in result.refusals] == [
        ("weight_lbs", REFUSAL_REASON_AMBIGUOUS_UNIT),
    ]
    assert result.source == "none"


def test_extract_with_telemetry_atomic_bp_partial_recorded() -> None:
    """An atomic-pair sweep that drops an orphan diastole is recorded as ``atomic_bp_partial``.

    Systole 20 < SDK floor 30 → refused with ``out_of_range``. Diastole 22 survives
    the per-field gate but is dropped by the atomic sweep. The orphan record carries
    ``atomic_bp_partial`` reason. Both fields land in refusals.
    """
    parser = VitalsParser()
    obs = [
        _loinc_obs("8480-6", "20", unit="mmHg", display="Systolic BP"),
        _loinc_obs("8462-4", "22", unit="mmHg", display="Diastolic BP"),
    ]
    result = parser.extract_with_telemetry("", obs)
    refusal_map = {r.field: r.reason for r in result.refusals}
    assert refusal_map == {
        "blood_pressure_systole": REFUSAL_REASON_OUT_OF_RANGE,
        "blood_pressure_diastole": REFUSAL_REASON_ATOMIC_BP_PARTIAL,
    }


def test_extract_with_telemetry_bp_panel_fully_refused_yields_source_none() -> None:
    """Fix 2: fully-refused BP-panel observation must classify as source=none, not observations.

    Risk-hunter scenario: Nabla emits a single BP-panel observation with both halves
    out of range (BP 999/999). The per-field gate refuses both. With no other
    observations and no regex text, the FINAL data is empty → source must be ``none``,
    NOT ``observations``. This catches the race the prior implementation had: the
    classifier looked at the raw input ``observations`` having entries, not at what
    actually survived validation.
    """
    parser = VitalsParser()
    obs = [_loinc_obs("85354-9", "999/999", unit="mmHg", display="Blood pressure")]
    result = parser.extract_with_telemetry("", obs)
    assert result.proposal is None
    assert result.source == "none"
    # Both halves are recorded as out-of-range refusals.
    refusal_map = {r.field: r.reason for r in result.refusals}
    assert refusal_map == {
        "blood_pressure_systole": REFUSAL_REASON_OUT_OF_RANGE,
        "blood_pressure_diastole": REFUSAL_REASON_OUT_OF_RANGE,
    }


def test_extract_with_telemetry_source_classified_from_final_survivors() -> None:
    """source=both requires BOTH paths to contribute SURVIVING fields, not raw inputs.

    Nabla emits a fully-refused BP observation (both halves out of range).
    The regex text provides a valid HR. Final survivors: only HR (regex).
    Source must be ``regex``, NOT ``both`` — even though both raw paths
    had inputs, only the regex contributed survivors.
    """
    parser = VitalsParser()
    obs = [_loinc_obs("85354-9", "999/999", unit="mmHg", display="Blood pressure")]
    result = parser.extract_with_telemetry("HR 74", obs)
    assert result.proposal is not None
    assert result.proposal.data == {"pulse": 74}
    assert result.source == "regex"
