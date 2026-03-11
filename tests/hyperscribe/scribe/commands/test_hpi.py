from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.hpi import HpiParser


def test_extract() -> None:
    parser = HpiParser()
    proposal = parser.extract("Pain radiates down left leg. Onset 2 weeks ago.")
    assert proposal is not None
    assert proposal.command_type == "hpi"
    assert proposal.data["narrative"] == "Pain radiates down left leg. Onset 2 weeks ago."
    assert proposal.display == "Pain radiates down left leg. Onset 2 weeks ago."
    assert proposal.selected is True


def test_build() -> None:
    parser = HpiParser()
    with patch("hyperscribe.scribe.commands.hpi.HistoryOfPresentIllnessCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"narrative": "Headaches for two weeks."}, "note-uuid-123", "cmd-uuid")

    mock_cmd.assert_called_once_with(
        narrative="Headaches for two weeks.", note_uuid="note-uuid-123", command_uuid="cmd-uuid"
    )


def test_build_missing_data_defaults() -> None:
    parser = HpiParser()
    with patch("hyperscribe.scribe.commands.hpi.HistoryOfPresentIllnessCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(narrative="", note_uuid="note-uuid", command_uuid="cmd-uuid")
