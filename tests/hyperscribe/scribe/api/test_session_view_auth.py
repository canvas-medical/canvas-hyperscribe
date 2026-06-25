import json
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.v1.data.note import Note as RealNote

from hyperscribe.scribe.api.session_view import _authorize_edit, _authorize_read


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


# ---------------------------------------------------------------------------
# _authorize_read (KOALA-5689): read-only display sync. Confirms the note
# exists; intentionally does NOT check staff-is-provider or editable_note.
# Access scoping is delegated to the home-app's outer chart-access permissions
# — any staff who can load the patient's chart (MAs, supervisors, providers)
# legitimately needs to see the same ADDITIONAL COMMANDS view.
# ---------------------------------------------------------------------------


def _read_note_dict() -> dict[str, object]:
    """``_authorize_read`` only confirms existence via ``.values("dbid")``."""
    return {"dbid": 42}


def test_authorize_read_missing_note_uuid_returns_400() -> None:
    """Empty note_uuid short-circuits with 400 before any DB hit."""
    result = _authorize_read("", _request())
    assert result is not None
    assert result.status_code == HTTPStatus.BAD_REQUEST
    assert "note_uuid" in json.loads(result.content)["error"]


@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_read_note_not_found_returns_404(mock_note: MagicMock) -> None:
    """Unknown note id resolves as 404 — cheap diagnostic that distinguishes
    a typo'd id from a permission issue (the chart-access permission is
    upstream of this endpoint anyway)."""
    mock_note.objects.values.return_value.get.side_effect = RealNote.DoesNotExist
    mock_note.DoesNotExist = RealNote.DoesNotExist

    result = _authorize_read("note-uuid", _request())
    assert result is not None
    assert result.status_code == HTTPStatus.NOT_FOUND
    assert json.loads(result.content) == {"error": "Note not found"}


@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=False)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_read_signed_note_returns_none(mock_note: MagicMock, editable: MagicMock) -> None:
    """The KOALA-5689 bug scenario: a signed (non-editable) note must still
    be readable.

    This test would FAIL against ``_authorize_edit`` because ``editable_note()``
    returns False post-sign and ``_authorize_edit`` rejects with 403. It PASSES
    against ``_authorize_read`` because the editable_note() gate is dropped.

    We pin this explicitly because it's the whole point of the helper — if
    someone reintroduces an editability gate here (e.g. for "consistency"
    with the edit helper), the Scribe tab regresses to stale ADDITIONAL
    COMMANDS post-sign.
    """
    mock_note.objects.values.return_value.get.return_value = _read_note_dict()

    result = _authorize_read("note-uuid", _request())
    assert result is None
    # Crucially, the read path must NOT call editable_note() — it should be
    # blind to note signing state.
    editable.assert_not_called()
    # And the query must only confirm existence (single cheap column).
    mock_note.objects.values.assert_called_once_with("dbid")


@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=True)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_read_open_note_returns_none(mock_note: MagicMock, editable: MagicMock) -> None:
    """Baseline: an open, editable note is also readable. Both
    ``_authorize_edit`` and ``_authorize_read`` accept this case; keeping the
    pin guards against accidental tightening of the read path (e.g. someone
    adding a non-editable-but-not-signed exclusion).
    """
    mock_note.objects.values.return_value.get.return_value = _read_note_dict()

    result = _authorize_read("note-uuid", _request())
    assert result is None
    # Same blindness contract regardless of editability state.
    editable.assert_not_called()


@patch("hyperscribe.scribe.api.session_view.Helper.editable_note", return_value=True)
@patch("hyperscribe.scribe.api.session_view.Note")
def test_authorize_read_any_staff_succeeds(mock_note: MagicMock, editable: MagicMock) -> None:
    """Regression guard: the staff-is-provider check is GONE.

    Reads must succeed regardless of which staff is asking — covering MAs,
    supervisors, scribes, and the note's own provider all hit the same
    endpoint and must all see the same ADDITIONAL COMMANDS view. Access
    scoping is delegated to the home-app's outer chart-access permissions.

    Setup: request carries a staff_id that does NOT match any provider on
    the (mocked) note. A future "let me lock this down" PR that re-adds an
    author-only check will trip this test.
    """
    mock_note.objects.values.return_value.get.return_value = _read_note_dict()

    result = _authorize_read("note-uuid", _request("not-the-provider"))
    assert result is None
    # No editable_note() check, no provider/staff comparison — just existence.
    editable.assert_not_called()
    mock_note.objects.values.assert_called_once_with("dbid")
