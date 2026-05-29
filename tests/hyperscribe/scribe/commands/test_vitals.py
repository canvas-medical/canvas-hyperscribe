from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.vitals import VitalsParser, _parse_vitals


def test_extract_basic() -> None:
    parser = VitalsParser()
    proposal = parser.extract("BP 120/80, HR 72, RR 16, SpO2 98%")
    assert proposal is not None
    assert proposal.command_type == "vitals"
    assert proposal.data["blood_pressure_systole"] == 120
    assert proposal.data["blood_pressure_diastole"] == 80
    assert proposal.data["pulse"] == 72
    assert proposal.data["respiration_rate"] == 16
    assert proposal.data["oxygen_saturation"] == 98
    assert proposal.display == "BP 120/80, HR 72, RR 16, SpO2 98%"
    assert proposal.selected is True


def test_extract_no_parseable_returns_none() -> None:
    parser = VitalsParser()
    assert parser.extract("Patient appears well.") is None


def test_parse_vitals_blood_pressure() -> None:
    result = _parse_vitals("BP 130 / 85")
    assert result["blood_pressure_systole"] == 130
    assert result["blood_pressure_diastole"] == 85


def test_parse_vitals_all_fields() -> None:
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
    assert _parse_vitals("Patient appears well.") == {}


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
