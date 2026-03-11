from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.rfv import RfvParser


def test_extract() -> None:
    parser = RfvParser()
    proposal = parser.extract("Patient presents with lower back pain.")
    assert proposal is not None
    assert proposal.command_type == "rfv"
    assert proposal.data["comment"] == "Patient presents with lower back pain."
    assert proposal.display == "Patient presents with lower back pain."
    assert proposal.selected is True


def test_build() -> None:
    parser = RfvParser()
    with patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"comment": "Lower back pain."}, "note-uuid-456", "cmd-uuid")

    mock_cmd.assert_called_once_with(comment="Lower back pain.", note_uuid="note-uuid-456", command_uuid="cmd-uuid")


def test_build_missing_data_defaults() -> None:
    parser = RfvParser()
    with patch("hyperscribe.scribe.commands.rfv.ReasonForVisitCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid", "cmd-uuid")

    mock_cmd.assert_called_once_with(comment="", note_uuid="note-uuid", command_uuid="cmd-uuid")
