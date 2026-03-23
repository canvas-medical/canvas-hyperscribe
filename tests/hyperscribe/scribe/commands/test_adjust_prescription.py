from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.adjust_prescription import AdjustPrescriptionParser


def test_extract_returns_none() -> None:
    parser = AdjustPrescriptionParser()
    assert parser.extract("some text") is None


def test_extract_all_returns_empty() -> None:
    parser = AdjustPrescriptionParser()
    assert parser.extract_all("some text") == []


def test_build_with_all_fields() -> None:
    parser = AdjustPrescriptionParser()
    data = {
        "fdb_code": "285665",
        "sig": "Take 1 tablet daily",
        "days_supply": 30,
        "quantity_to_dispense": 30,
        "refills": 2,
        "substitutions": "allowed",
    }
    with patch("hyperscribe.scribe.commands.adjust_prescription.AdjustPrescriptionCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        mock_cmd.Substitutions = MagicMock()
        mock_cmd.Substitutions.ALLOWED = "ALLOWED"
        mock_cmd.Substitutions.NOT_ALLOWED = "NOT_ALLOWED"
        with patch.object(parser, "_resolve_prescriber", return_value="provider-123"):
            parser.build(data, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once()
    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["fdb_code"] == "285665"
    assert call_kwargs["sig"] == "Take 1 tablet daily"
    assert call_kwargs["note_uuid"] == "note-uuid"


def test_build_with_missing_fields() -> None:
    parser = AdjustPrescriptionParser()
    with patch("hyperscribe.scribe.commands.adjust_prescription.AdjustPrescriptionCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        with patch.object(parser, "_resolve_prescriber", return_value=None):
            parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once()
    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["fdb_code"] is None
    assert call_kwargs["sig"] == ""


def test_command_type() -> None:
    assert AdjustPrescriptionParser().command_type == "adjust_prescription"


def test_data_field_is_none() -> None:
    assert AdjustPrescriptionParser().data_field is None


def test_to_effects_returns_originate_and_review() -> None:
    parser = AdjustPrescriptionParser()
    command = MagicMock()
    command.originate.return_value = MagicMock()
    command.review.return_value = MagicMock()

    effects = parser.to_effects(command)

    assert len(effects) == 2
    command.originate.assert_called_once()
    command.review.assert_called_once()
