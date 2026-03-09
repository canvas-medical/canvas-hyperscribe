from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.builder import build_effects


def test_build_hpi_effect() -> None:
    proposals = [{"command_type": "hpi", "data": {"narrative": "Headaches for two weeks."}}]
    with patch("hyperscribe.scribe.commands.builder.HistoryOfPresentIllnessCommand") as mock_cmd:
        mock_instance = MagicMock()
        mock_cmd.return_value = mock_instance
        mock_instance.originate.return_value = "hpi_effect"

        effects = build_effects(proposals, "note-uuid-123")

    mock_cmd.assert_called_once_with(narrative="Headaches for two weeks.", note_uuid="note-uuid-123")
    mock_instance.originate.assert_called_once()
    assert effects == ["hpi_effect"]


def test_build_plan_effect() -> None:
    proposals = [{"command_type": "plan", "data": {"narrative": "Start sumatriptan 50mg."}}]
    with patch("hyperscribe.scribe.commands.builder.PlanCommand") as mock_cmd:
        mock_instance = MagicMock()
        mock_cmd.return_value = mock_instance
        mock_instance.originate.return_value = "plan_effect"

        effects = build_effects(proposals, "note-uuid-123")

    mock_cmd.assert_called_once_with(narrative="Start sumatriptan 50mg.", note_uuid="note-uuid-123")
    mock_instance.originate.assert_called_once()
    assert effects == ["plan_effect"]


def test_build_rfv_effect() -> None:
    proposals = [{"command_type": "rfv", "data": {"comment": "Lower back pain."}}]
    with patch("hyperscribe.scribe.commands.builder.ReasonForVisitCommand") as mock_cmd:
        mock_instance = MagicMock()
        mock_cmd.return_value = mock_instance
        mock_instance.originate.return_value = "rfv_effect"

        effects = build_effects(proposals, "note-uuid-456")

    mock_cmd.assert_called_once_with(comment="Lower back pain.", note_uuid="note-uuid-456")
    mock_instance.originate.assert_called_once()
    assert effects == ["rfv_effect"]


def test_build_effects_multiple() -> None:
    proposals = [
        {"command_type": "rfv", "data": {"comment": "Headache"}},
        {"command_type": "hpi", "data": {"narrative": "Two weeks of headaches"}},
        {"command_type": "plan", "data": {"narrative": "Start sumatriptan"}},
    ]
    with (
        patch("hyperscribe.scribe.commands.builder.ReasonForVisitCommand") as mock_rfv,
        patch("hyperscribe.scribe.commands.builder.HistoryOfPresentIllnessCommand") as mock_hpi,
        patch("hyperscribe.scribe.commands.builder.PlanCommand") as mock_plan,
    ):
        for mock in [mock_rfv, mock_hpi, mock_plan]:
            inst = MagicMock()
            inst.originate.return_value = f"{mock._mock_name}_effect"
            mock.return_value = inst

        effects = build_effects(proposals, "note-uuid")

    assert len(effects) == 3
    mock_rfv.assert_called_once()
    mock_hpi.assert_called_once()
    mock_plan.assert_called_once()


def test_build_effects_unknown_type_skipped() -> None:
    proposals = [{"command_type": "unknown_type", "data": {"foo": "bar"}}]
    effects = build_effects(proposals, "note-uuid")
    assert effects == []


def test_build_effects_empty_list() -> None:
    effects = build_effects([], "note-uuid")
    assert effects == []


def test_build_effects_missing_data_defaults() -> None:
    proposals = [{"command_type": "hpi", "data": {}}]
    with patch("hyperscribe.scribe.commands.builder.HistoryOfPresentIllnessCommand") as mock_cmd:
        mock_instance = MagicMock()
        mock_cmd.return_value = mock_instance
        mock_instance.originate.return_value = "effect"

        effects = build_effects(proposals, "note-uuid")

    mock_cmd.assert_called_once_with(narrative="", note_uuid="note-uuid")
    assert effects == ["effect"]
