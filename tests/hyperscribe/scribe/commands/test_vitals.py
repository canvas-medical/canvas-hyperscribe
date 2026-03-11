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
    }
    with patch("hyperscribe.scribe.commands.vitals.VitalsCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid-789", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        height=None,
        weight_lbs=None,
        body_temperature=None,
        blood_pressure_systole=120,
        blood_pressure_diastole=80,
        pulse=72,
        respiration_rate=16,
        oxygen_saturation=98,
        note_uuid="note-uuid-789",
        command_uuid="cmd-uuid",
    )
