from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.lab_order import LabOrderParser


def test_extract() -> None:
    parser = LabOrderParser()
    proposal = parser.extract("CBC with differential")
    assert proposal is not None
    assert proposal.command_type == "lab_order"
    assert proposal.data["comment"] == "CBC with differential"
    assert proposal.display == "CBC with differential"


def test_extract_empty_returns_empty_comment() -> None:
    parser = LabOrderParser()
    proposal = parser.extract("")
    assert proposal is not None
    assert proposal.data["comment"] == ""


def test_build() -> None:
    parser = LabOrderParser()
    with patch("hyperscribe.scribe.commands.lab_order.LabOrderCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"comment": "CBC with differential"}, "note-uuid")

    mock_cmd.assert_called_once_with(comment="CBC with differential", note_uuid="note-uuid")


def test_build_empty_comment() -> None:
    parser = LabOrderParser()
    with patch("hyperscribe.scribe.commands.lab_order.LabOrderCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid")

    mock_cmd.assert_called_once_with(comment=None, note_uuid="note-uuid")
