import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.effects.simple_api import JSONResponse
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPI

from hyperscribe.scribe.api.session_view import ScribeSessionView
from hyperscribe.scribe.backend import ScribeError
from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    CodingEntry,
    Condition,
    NormalizedData,
    NoteSection,
    Observation,
)

# Disable automatic route resolution
ScribeSessionView._ROUTES = {}


def _helper_instance() -> ScribeSessionView:
    event = SimpleNamespace(context={"method": "GET"})
    secrets: dict[str, str] = {"ScribeBackend": '{"vendor": "nabla", "client_id": "id", "client_secret": "secret"}'}
    environment: dict[str, str] = {}
    view = ScribeSessionView(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    return view


def test_class() -> None:
    assert issubclass(ScribeSessionView, SimpleAPI)


def test_constants() -> None:
    assert ScribeSessionView.PREFIX == "/scribe-session"


def test_authenticate() -> None:
    view = _helper_instance()
    assert view.authenticate(Credentials(SimpleNamespace())) is True


# --- /config ---


@patch("hyperscribe.scribe.api.session_view._get_provider_key", return_value="staff-key-abc")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_success(get_backend: MagicMock, _get_key: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.get_transcription_config.return_value = {
        "vendor": "nabla",
        "ws_url": "wss://example.com/ws",
        "access_token": "tok",
        "sample_rate": 16000,
    }
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_dbid": ["42"]})
    result = view.get_config()

    expected = [
        JSONResponse(
            {"vendor": "nabla", "ws_url": "wss://example.com/ws", "access_token": "tok", "sample_rate": 16000},
            status_code=HTTPStatus.OK,
        )
    ]
    assert result == expected
    mock_backend.get_transcription_config.assert_called_once_with(user_external_id="staff-key-abc")


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_no_note_dbid(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.get_transcription_config.return_value = {"vendor": "nabla"}
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_config()

    assert result[0].status_code == HTTPStatus.OK
    mock_backend.get_transcription_config.assert_called_once_with(user_external_id="")


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_unknown_vendor(get_backend: MagicMock) -> None:
    get_backend.side_effect = ScribeError("Unknown scribe vendor: 'bad'")

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_config()

    expected = [JSONResponse({"error": "Unknown scribe vendor: 'bad'"}, status_code=HTTPStatus.BAD_REQUEST)]
    assert result == expected


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_auth_error(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.get_transcription_config.side_effect = ScribeError("Auth failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_config()

    expected = [JSONResponse({"error": "Auth failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected


# --- /generate-note ---


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_success(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[NoteSection(key="subjective", title="Subjective", text="Headache.")],
    )
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "transcript": {
                    "items": [
                        {"text": "I have a headache", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 2000}
                    ]
                }
            }
        )
    )
    result = view.post_generate_note()

    expected = [
        JSONResponse(
            {
                "title": "SOAP Note",
                "sections": [{"key": "subjective", "title": "Subjective", "text": "Headache."}],
            },
            status_code=HTTPStatus.OK,
        )
    ]
    assert result == expected
    mock_backend.generate_note.assert_called_once()


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_with_patient_context(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(title="Note", sections=[])
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "transcript": {"items": []},
                "patient_context": {
                    "name": "Jane Doe",
                    "birth_date": "1990-01-01",
                    "gender": "female",
                    "encounter_diagnoses": [{"system": "ICD-10", "code": "R51", "display": "Headache"}],
                },
            }
        )
    )
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.OK
    call_kwargs = mock_backend.generate_note.call_args
    patient_ctx = call_kwargs.kwargs["patient_context"]
    assert patient_ctx.name == "Jane Doe"
    assert patient_ctx.encounter_diagnoses[0].code == "R51"


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_invalid_json(get_backend: MagicMock) -> None:
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_backend_error(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_note.side_effect = ScribeError("Note generation failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"transcript": {"items": []}}))
    result = view.post_generate_note()

    expected = [JSONResponse({"error": "Note generation failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected


# --- /generate-normalized-data ---


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_normalized_data_success(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_normalized_data.return_value = NormalizedData(
        conditions=[
            Condition(
                display="Headache",
                clinical_status="active",
                coding=[CodingEntry(system="ICD-10", code="R51", display="Headache")],
            )
        ],
        observations=[
            Observation(
                display="BP",
                value="120/80",
                unit="mmHg",
                coding=[CodingEntry(system="LOINC", code="85354-9", display="Blood pressure")],
            )
        ],
    )
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "SOAP Note",
                    "sections": [{"key": "subjective", "title": "Subjective", "text": "Headache."}],
                }
            }
        )
    )
    result = view.post_generate_normalized_data()

    assert result[0].status_code == HTTPStatus.OK
    response_data = json.loads(result[0].content)
    assert len(response_data["conditions"]) == 1
    assert response_data["conditions"][0]["display"] == "Headache"
    assert response_data["conditions"][0]["coding"][0]["code"] == "R51"
    assert len(response_data["observations"]) == 1
    assert response_data["observations"][0]["value"] == "120/80"


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_normalized_data_invalid_json(get_backend: MagicMock) -> None:
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body="bad-json")
    result = view.post_generate_normalized_data()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_normalized_data_backend_error(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_normalized_data.side_effect = ScribeError("Normalization failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Note", "sections": []}}))
    result = view.post_generate_normalized_data()

    expected = [JSONResponse({"error": "Normalization failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected
