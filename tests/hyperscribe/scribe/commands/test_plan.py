from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.plan import PlanParser


def test_extract() -> None:
    parser = PlanParser()
    proposal = parser.extract("Start naproxen 500mg BID. Order lumbar MRI.")
    assert proposal is not None
    assert proposal.command_type == "plan"
    assert proposal.data["narrative"] == "Start naproxen 500mg BID. Order lumbar MRI."
    assert proposal.display == "Start naproxen 500mg BID. Order lumbar MRI."
    assert proposal.selected is True


def test_build() -> None:
    parser = PlanParser()
    with patch("hyperscribe.scribe.commands.plan.PlanCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({"narrative": "Start sumatriptan 50mg."}, "note-uuid-123")

    mock_cmd.assert_called_once_with(narrative="Start sumatriptan 50mg.", note_uuid="note-uuid-123")


def test_build_missing_data_defaults() -> None:
    parser = PlanParser()
    with patch("hyperscribe.scribe.commands.plan.PlanCommand") as mock_cmd:
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid")

    mock_cmd.assert_called_once_with(narrative="", note_uuid="note-uuid")
