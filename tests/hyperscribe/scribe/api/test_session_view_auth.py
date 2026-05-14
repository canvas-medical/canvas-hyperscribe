import json
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.core.exceptions import ValidationError

from canvas_sdk.v1.data.note import Note as RealNote

from hyperscribe.scribe.api.session_view import _authorize_edit, _authorize_read_as_author


def _note_dict(dbid: int, provider_id: str | None) -> dict[str, object]:
    return {"dbid": dbid, "provider__id": provider_id}


def _request(staff_id: str = "staff-1") -> SimpleNamespace:
    return SimpleNamespace(headers={"canvas-logged-in-user-id": staff_id} if staff_id else {})


def test_authorize_edit_missing_note_uuid() -> None:
    result = _authorize_edit("", _request())
    assert result is not None
    assert result.status_code == HTTPStatus.BAD_REQUEST
    assert "note_uuid" in json.loads(result.content)["error"]


@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_edit_note_not_found(mock_note: MagicMock) -> None:
    mock_note.objects.values.return_value.get.side_effect = RealNote.DoesNotExist
    mock_note.DoesNotExist = RealNote.DoesNotExist

    result = _authorize_edit("note-uuid", _request())
    assert result is not None
    assert result.status_code == HTTPStatus.NOT_FOUND
    assert json.loads(result.content) == {"error": "Note not found"}


@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=False)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_edit_note_not_editable(mock_note: MagicMock, _editable: MagicMock) -> None:
    mock_note.objects.values.return_value.get.return_value = _note_dict(42, "staff-1")

    result = _authorize_edit("note-uuid", _request())
    assert result is not None
    assert result.status_code == HTTPStatus.FORBIDDEN
    assert "not editable" in json.loads(result.content)["error"]


@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=True)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_edit_no_provider(mock_note: MagicMock, _editable: MagicMock) -> None:
    mock_note.objects.values.return_value.get.return_value = _note_dict(42, None)

    result = _authorize_edit("note-uuid", _request())
    assert result is not None
    assert result.status_code == HTTPStatus.FORBIDDEN
    assert "note author" in json.loads(result.content)["error"]


@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=True)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_edit_different_provider(mock_note: MagicMock, _editable: MagicMock) -> None:
    mock_note.objects.values.return_value.get.return_value = _note_dict(42, "other-staff")

    result = _authorize_edit("note-uuid", _request("staff-1"))
    assert result is not None
    assert result.status_code == HTTPStatus.FORBIDDEN
    assert "note author" in json.loads(result.content)["error"]


@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=True)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_edit_missing_staff_id(mock_note: MagicMock, _editable: MagicMock) -> None:
    mock_note.objects.values.return_value.get.return_value = _note_dict(42, "staff-1")

    result = _authorize_edit("note-uuid", _request(""))
    assert result is not None
    assert result.status_code == HTTPStatus.FORBIDDEN


@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=True)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_edit_matching_provider(mock_note: MagicMock, editable: MagicMock) -> None:
    mock_note.objects.values.return_value.get.return_value = _note_dict(42, "staff-1")

    result = _authorize_edit("note-uuid", _request("staff-1"))
    assert result is None
    editable.assert_called_once_with(42)
    mock_note.objects.values.assert_called_once_with("dbid", "provider__id")


@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_edit_non_uuid_note_uuid_returns_not_found(mock_note: MagicMock) -> None:
    """A non-UUID note_uuid must not crash the endpoint. Django's UUIDField
    raises ValidationError during query preparation; the helper must treat it
    the same as 'not found' so a malformed direct-API caller doesn't 500
    instead of getting a clean 404."""
    mock_note.objects.values.return_value.get.side_effect = ValidationError(
        "“not-a-real-uuid” is not a valid UUID."
    )
    mock_note.DoesNotExist = RealNote.DoesNotExist

    result = _authorize_edit("not-a-real-uuid", _request())
    assert result is not None
    assert result.status_code == HTTPStatus.NOT_FOUND
    assert json.loads(result.content) == {"error": "Note not found"}


@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_read_as_author_non_uuid_note_uuid_returns_not_found(mock_note: MagicMock) -> None:
    """Same ValidationError protection as _authorize_edit, applied to the
    read-only helper used by /verify-commands."""
    mock_note.objects.values.return_value.get.side_effect = ValidationError(
        "“not-a-real-uuid” is not a valid UUID."
    )
    mock_note.DoesNotExist = RealNote.DoesNotExist

    result = _authorize_read_as_author("not-a-real-uuid", _request())
    assert result is not None
    assert result.status_code == HTTPStatus.NOT_FOUND
    assert json.loads(result.content) == {"error": "Note not found"}
