from unittest.mock import MagicMock, patch

from hyperscribe.scribe.commands.imaging_order import ImagingOrderParser


def test_extract_returns_none() -> None:
    parser = ImagingOrderParser()
    assert parser.extract("MRI lumbar spine") is None


def test_build_routine() -> None:
    parser = ImagingOrderParser()
    data = {"comment": "MRI lumbar spine", "priority": "Routine"}
    with patch("hyperscribe.scribe.commands.imaging_order.ImagingOrderCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.Priority.ROUTINE = "ROUTINE"
        mock_cmd.Priority.URGENT = "URGENT"
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid")

    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["comment"] == "MRI lumbar spine"
    assert call_kwargs["priority"] == "ROUTINE"
    assert call_kwargs["note_uuid"] == "note-uuid"


def test_build_urgent() -> None:
    parser = ImagingOrderParser()
    data = {"comment": "CT head", "priority": "Urgent"}
    with patch("hyperscribe.scribe.commands.imaging_order.ImagingOrderCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.Priority.ROUTINE = "ROUTINE"
        mock_cmd.Priority.URGENT = "URGENT"
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid")

    assert mock_cmd.call_args.kwargs["priority"] == "URGENT"


def test_build_no_priority() -> None:
    parser = ImagingOrderParser()
    data = {"comment": "X-ray chest"}
    with patch("hyperscribe.scribe.commands.imaging_order.ImagingOrderCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.return_value = MagicMock()
        parser.build(data, "note-uuid")

    assert mock_cmd.call_args.kwargs["priority"] is None


def test_build_empty_data() -> None:
    parser = ImagingOrderParser()
    with patch("hyperscribe.scribe.commands.imaging_order.ImagingOrderCommand") as mock_cmd:
        mock_cmd.Priority = MagicMock()
        mock_cmd.return_value = MagicMock()
        parser.build({}, "note-uuid")

    call_kwargs = mock_cmd.call_args.kwargs
    assert call_kwargs["comment"] is None
    assert call_kwargs["priority"] is None
