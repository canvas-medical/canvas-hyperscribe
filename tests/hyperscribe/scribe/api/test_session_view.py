import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.effects.simple_api import JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, Credentials

from hyperscribe.scribe.api import session_view
from hyperscribe.scribe.api.session_view import ScribeSessionView, _get_or_create_backend, _clear_backend
from hyperscribe.scribe.backend import ScribeError, TranscriptItem, Transcript

# Disable automatic route resolution
ScribeSessionView._ROUTES = {}


def helper_instance() -> ScribeSessionView:
    event = SimpleNamespace(context={"method": "GET"})
    secrets: dict[str, str] = {"ScribeBackend": '{"vendor": "nabla", "client_id": "id", "client_secret": "secret"}'}
    environment: dict[str, str] = {}
    view = ScribeSessionView(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    return view


def _reset_backend() -> None:
    session_view._backend = None


def test_class() -> None:
    assert issubclass(ScribeSessionView, SimpleAPI)


def test_constants() -> None:
    assert ScribeSessionView.PREFIX == "/scribe-session"


def test_authenticate() -> None:
    view = helper_instance()
    assert view.authenticate(Credentials(SimpleNamespace())) is True


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_or_create_backend_caches(get_backend: MagicMock) -> None:
    _reset_backend()
    mock_backend = MagicMock()
    get_backend.return_value = mock_backend
    secrets: dict[str, str] = {"ScribeBackend": '{"vendor": "nabla"}'}

    first = _get_or_create_backend(secrets)
    second = _get_or_create_backend(secrets)

    assert first is mock_backend
    assert second is mock_backend
    assert get_backend.call_count == 1
    _reset_backend()


def test_clear_backend() -> None:
    session_view._backend = MagicMock()
    assert session_view._backend is not None
    _clear_backend()
    assert session_view._backend is None


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_start_success(get_backend: MagicMock) -> None:
    _reset_backend()
    mock_backend = MagicMock()
    get_backend.return_value = mock_backend

    view = helper_instance()
    result = view.start()

    expected = [JSONResponse({"status": "started"}, status_code=HTTPStatus.OK)]
    assert result == expected
    mock_backend.start_session.assert_called_once()
    _reset_backend()


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_start_unknown_vendor(get_backend: MagicMock) -> None:
    _reset_backend()
    get_backend.side_effect = ScribeError("Unknown scribe vendor: 'bad'")

    view = helper_instance()
    result = view.start()

    expected = [JSONResponse({"error": "Unknown scribe vendor: 'bad'"}, status_code=HTTPStatus.BAD_REQUEST)]
    assert result == expected
    _reset_backend()


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_start_session_error(get_backend: MagicMock) -> None:
    _reset_backend()
    mock_backend = MagicMock()
    mock_backend.start_session.side_effect = ScribeError("Connection failed")
    get_backend.return_value = mock_backend

    view = helper_instance()
    result = view.start()

    expected = [JSONResponse({"error": "Connection failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected
    _reset_backend()


def test_audio_no_active_session() -> None:
    _reset_backend()
    view = helper_instance()
    result = view.audio()

    expected = [JSONResponse({"error": "No active session"}, status_code=HTTPStatus.CONFLICT)]
    assert result == expected


def test_audio_missing_form_part() -> None:
    _reset_backend()
    mock_backend = MagicMock()
    session_view._backend = mock_backend

    view = helper_instance()
    view.request = SimpleNamespace(form_data=lambda: {})
    result = view.audio()

    expected = [JSONResponse({"error": "Missing 'audio' form part"}, status_code=HTTPStatus.BAD_REQUEST)]
    assert result == expected
    _reset_backend()


def test_audio_success() -> None:
    _reset_backend()
    mock_backend = MagicMock()
    session_view._backend = mock_backend

    view = helper_instance()
    view.request = SimpleNamespace(
        form_data=lambda: {"audio": SimpleNamespace(content=b"audio-data")},
    )
    result = view.audio()

    expected = [JSONResponse({"status": "ok"}, status_code=HTTPStatus.ACCEPTED)]
    assert result == expected
    mock_backend.send_audio.assert_called_once_with(b"audio-data")
    _reset_backend()


def test_audio_send_error() -> None:
    _reset_backend()
    mock_backend = MagicMock()
    mock_backend.send_audio.side_effect = ScribeError("Send failed")
    session_view._backend = mock_backend

    view = helper_instance()
    view.request = SimpleNamespace(
        form_data=lambda: {"audio": SimpleNamespace(content=b"audio-data")},
    )
    result = view.audio()

    expected = [JSONResponse({"error": "Send failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected
    _reset_backend()


def test_transcript_no_active_session() -> None:
    _reset_backend()
    view = helper_instance()
    result = view.transcript()

    expected = [JSONResponse({"error": "No active session"}, status_code=HTTPStatus.CONFLICT)]
    assert result == expected


def test_transcript_success() -> None:
    _reset_backend()
    mock_backend = MagicMock()
    mock_backend.get_transcript_updates.return_value = [
        TranscriptItem(
            text="Hello doctor",
            speaker="patient",
            start_offset_ms=0,
            end_offset_ms=1500,
            item_id="item-1",
            is_final=True,
        ),
        TranscriptItem(
            text="How are you",
            speaker="provider",
            start_offset_ms=1600,
            end_offset_ms=3000,
            item_id="item-2",
            is_final=False,
        ),
    ]
    session_view._backend = mock_backend

    view = helper_instance()
    result = view.transcript()

    expected = [
        JSONResponse(
            {
                "items": [
                    {
                        "text": "Hello doctor",
                        "speaker": "patient",
                        "start_offset_ms": 0,
                        "end_offset_ms": 1500,
                        "item_id": "item-1",
                        "is_final": True,
                    },
                    {
                        "text": "How are you",
                        "speaker": "provider",
                        "start_offset_ms": 1600,
                        "end_offset_ms": 3000,
                        "item_id": "item-2",
                        "is_final": False,
                    },
                ],
            },
            status_code=HTTPStatus.OK,
        )
    ]
    assert result == expected
    _reset_backend()


def test_transcript_error() -> None:
    _reset_backend()
    mock_backend = MagicMock()
    mock_backend.get_transcript_updates.side_effect = ScribeError("Read failed")
    session_view._backend = mock_backend

    view = helper_instance()
    result = view.transcript()

    expected = [JSONResponse({"error": "Read failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected
    _reset_backend()


def test_end_no_active_session() -> None:
    _reset_backend()
    view = helper_instance()
    result = view.end()

    expected = [JSONResponse({"error": "No active session"}, status_code=HTTPStatus.CONFLICT)]
    assert result == expected


def test_end_success() -> None:
    _reset_backend()
    mock_backend = MagicMock()
    mock_backend.end_session.return_value = Transcript(
        items=[
            TranscriptItem(
                text="Final text",
                speaker="patient",
                start_offset_ms=0,
                end_offset_ms=5000,
                item_id="final-1",
                is_final=True,
            ),
        ]
    )
    session_view._backend = mock_backend

    view = helper_instance()
    result = view.end()

    expected = [
        JSONResponse(
            {
                "status": "ended",
                "transcript": {
                    "items": [
                        {
                            "text": "Final text",
                            "speaker": "patient",
                            "start_offset_ms": 0,
                            "end_offset_ms": 5000,
                            "item_id": "final-1",
                            "is_final": True,
                        },
                    ],
                },
            },
            status_code=HTTPStatus.OK,
        )
    ]
    assert result == expected
    assert session_view._backend is None  # cleared after end


def test_end_error_still_clears_backend() -> None:
    _reset_backend()
    mock_backend = MagicMock()
    mock_backend.end_session.side_effect = ScribeError("Close failed")
    session_view._backend = mock_backend

    view = helper_instance()
    result = view.end()

    expected = [JSONResponse({"error": "Close failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected
    assert session_view._backend is None  # cleared even on error
