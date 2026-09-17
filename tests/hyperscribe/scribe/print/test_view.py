import re
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.v1.data.note import Note as RealNote

from hyperscribe.scribe.print.view import PrintScribeNoteView

# Disable automatic route resolution (SimpleAPI parses these at class init normally).
PrintScribeNoteView._ROUTES = {}


def _view_instance() -> PrintScribeNoteView:
    event = SimpleNamespace(context={"method": "GET"})
    view = PrintScribeNoteView(event, {}, {})
    view._path_pattern = re.compile(r".*")
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": "staff-1"},
        path_params={"note_id": "42"},
        query_params={},
        body=b"",
    )
    return view


def test_class_prefix() -> None:
    assert PrintScribeNoteView.PREFIX == "/scribe-print"


def test_print_note_missing_note_id() -> None:
    view = _view_instance()
    view.request.path_params = {}

    result = view.print_note()

    assert len(result) == 1
    assert result[0].status_code == 400
    assert result[0].content == b"Missing note_id"


@patch("hyperscribe.scribe.print.view.Note")
def test_print_note_note_not_found(mock_note: MagicMock) -> None:
    mock_note.objects.get.side_effect = RealNote.DoesNotExist
    mock_note.DoesNotExist = RealNote.DoesNotExist

    view = _view_instance()
    result = view.print_note()

    assert len(result) == 1
    assert result[0].status_code == 404
    assert result[0].content == b"Note not found"


@patch("hyperscribe.scribe.print.view.ScribeSummary")
@patch("hyperscribe.scribe.print.view.Note")
def test_print_note_no_scribe_data(mock_note: MagicMock, mock_summary: MagicMock) -> None:
    mock_note.objects.get.return_value = MagicMock()
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = None

    view = _view_instance()
    result = view.print_note()

    assert len(result) == 1
    assert result[0].status_code == 404
    assert result[0].content == b"No Scribe data for this note"


@patch("hyperscribe.scribe.print.view.render_to_string")
@patch("hyperscribe.scribe.print.view.build_note_header_context")
@patch("hyperscribe.scribe.print.view.build_scribe_body_items")
@patch("hyperscribe.scribe.print.view.ScribeSummary")
@patch("hyperscribe.scribe.print.view.Note")
def test_print_note_happy_path(
    mock_note: MagicMock,
    mock_summary: MagicMock,
    mock_build_body: MagicMock,
    mock_build_header: MagicMock,
    mock_render: MagicMock,
) -> None:
    note_obj = MagicMock()
    mock_note.objects.get.return_value = note_obj
    summary_row = {
        "note_data": {"sections": []},
        "commands": [{"command_type": "task", "display": "Order labs"}],
        "recommendations": [],
        "approved": True,
    }
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = summary_row

    mock_build_body.return_value = [{"section_header": "OBJECTIVE"}]
    mock_build_header.return_value = {"patient_name": "Jane Doe"}
    mock_render.return_value = "<html>rendered</html>"

    view = _view_instance()
    result = view.print_note()

    assert len(result) == 1
    assert result[0].content == b"<html>rendered</html>"

    mock_note.objects.get.assert_called_once_with(dbid="42")
    mock_summary.objects.filter.assert_called_once_with(note_id="42")
    mock_build_body.assert_called_once_with(
        summary_row["note_data"], summary_row["commands"], summary_row["recommendations"]
    )
    mock_build_header.assert_called_once_with(note_obj)
    mock_render.assert_called_once_with(
        "scribe/print/templates/print_scribe_note.html",
        {"patient_name": "Jane Doe", "commands": [{"section_header": "OBJECTIVE"}]},
    )


@patch("hyperscribe.scribe.print.view.render_to_string", return_value="")
@patch("hyperscribe.scribe.print.view.build_note_header_context", return_value={})
@patch("hyperscribe.scribe.print.view.build_scribe_body_items", return_value=[])
@patch("hyperscribe.scribe.print.view.ScribeSummary")
@patch("hyperscribe.scribe.print.view.Note")
def test_print_note_render_failure(
    mock_note: MagicMock,
    mock_summary: MagicMock,
    _body: MagicMock,
    _header: MagicMock,
    _render: MagicMock,
) -> None:
    mock_note.objects.get.return_value = MagicMock()
    mock_summary.objects.filter.return_value.values.return_value.first.return_value = {
        "note_data": {},
        "commands": [],
        "recommendations": [],
        "approved": False,
    }

    view = _view_instance()
    result = view.print_note()

    assert len(result) == 1
    assert result[0].status_code == 500
    assert result[0].content == b"Template render failed"
