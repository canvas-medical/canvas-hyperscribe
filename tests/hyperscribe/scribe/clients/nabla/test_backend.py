from unittest.mock import MagicMock, patch

import pytest

from hyperscribe.scribe.backend import (
    ClinicalNote,
    CodingEntry,
    NormalizedData,
    NoteSection,
    PatientContext,
    ScribeBackend,
    ScribeTranscriptionError,
    Transcript,
    TranscriptItem,
)
from hyperscribe.scribe.clients.nabla.backend import NablaBackend


def _make_backend() -> tuple[NablaBackend, MagicMock, MagicMock]:
    with patch("hyperscribe.scribe.clients.nabla.backend.NablaAuth"):
        with patch("hyperscribe.scribe.clients.nabla.backend.NablaClient") as mock_client_cls:
            backend = NablaBackend(client_id="cid", client_secret="secret")
            mock_rest_client = mock_client_cls.return_value
    return backend, mock_rest_client, MagicMock()


def test_nabla_backend_is_scribe_backend():
    backend, _, _ = _make_backend()
    assert isinstance(backend, ScribeBackend)


def test_start_session():
    backend, _, _ = _make_backend()
    mock_ws = MagicMock()
    with patch("hyperscribe.scribe.clients.nabla.backend.NablaWsClient", return_value=mock_ws):
        backend.start_session()

    mock_ws.connect.assert_called_once()
    assert backend._ws_client is mock_ws


def test_send_audio():
    backend, _, _ = _make_backend()
    mock_ws = MagicMock()
    backend._ws_client = mock_ws

    backend.send_audio(b"raw-audio")

    mock_ws.send_audio_chunk.assert_called_once_with(b"raw-audio")


def test_send_audio_no_session():
    backend, _, _ = _make_backend()
    with pytest.raises(ScribeTranscriptionError, match="No active session"):
        backend.send_audio(b"audio-data")


def test_get_transcript_updates():
    backend, _, _ = _make_backend()
    mock_ws = MagicMock()
    items = [
        TranscriptItem(
            text="hello",
            speaker="patient",
            start_offset_ms=0,
            end_offset_ms=100,
            item_id="i1",
        ),
        TranscriptItem(
            text="hi",
            speaker="practitioner",
            start_offset_ms=100,
            end_offset_ms=200,
            item_id="i2",
            is_final=False,
        ),
    ]
    mock_ws.drain_items.return_value = items
    backend._ws_client = mock_ws

    result = backend.get_transcript_updates()

    assert result == items
    assert backend._session_items == items


def test_get_transcript_updates_no_session():
    backend, _, _ = _make_backend()
    assert backend.get_transcript_updates() == []


def test_end_session():
    backend, _, _ = _make_backend()
    mock_ws = MagicMock()
    backend._ws_client = mock_ws
    backend._session_items = [
        TranscriptItem(
            text="partial",
            speaker="patient",
            start_offset_ms=0,
            end_offset_ms=50,
            item_id="i1",
            is_final=False,
        ),
        TranscriptItem(
            text="final1",
            speaker="patient",
            start_offset_ms=0,
            end_offset_ms=100,
            item_id="i2",
            is_final=True,
        ),
    ]
    mock_ws.drain_items.return_value = [
        TranscriptItem(
            text="final2",
            speaker="practitioner",
            start_offset_ms=100,
            end_offset_ms=200,
            item_id="i3",
            is_final=True,
        ),
    ]

    result = backend.end_session()

    mock_ws.end.assert_called_once()
    assert isinstance(result, Transcript)
    assert len(result.items) == 2
    assert result.items[0].text == "final1"
    assert result.items[1].text == "final2"
    assert backend._ws_client is None
    assert backend._session_items == []


def test_end_session_no_session():
    backend, _, _ = _make_backend()
    with pytest.raises(ScribeTranscriptionError, match="No active session"):
        backend.end_session()


def test_generate_note():
    backend, mock_rest_client, _ = _make_backend()
    mock_rest_client.generate_note.return_value = {
        "title": "SOAP Note",
        "sections": [
            {"key": "subjective", "title": "Subjective", "text": "Patient reports headache."},
            {"key": "objective", "title": "Objective", "text": "BP 120/80."},
        ],
    }

    transcript = Transcript(items=[TranscriptItem(text="hi", speaker="patient", start_offset_ms=0, end_offset_ms=100)])
    result = backend.generate_note(transcript)

    assert isinstance(result, ClinicalNote)
    assert result.title == "SOAP Note"
    assert len(result.sections) == 2
    assert result.sections[0].key == "subjective"

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template"] == "SOAP"
    assert payload["locale"] == "en-US"
    assert len(payload["transcript"]["items"]) == 1


def test_generate_note_with_patient_context():
    backend, mock_rest_client, _ = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    ctx = PatientContext(
        name="Jane Doe",
        birth_date="1990-05-15",
        gender="female",
        encounter_diagnoses=[CodingEntry(system="ICD-10", code="R51", display="Headache")],
    )
    backend.generate_note(Transcript(), patient_context=ctx)

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["patient_context"]["name"] == "Jane Doe"
    assert payload["patient_context"]["encounter_diagnoses"][0]["code"] == "R51"


def test_generate_note_without_patient_context():
    backend, mock_rest_client, _ = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert "patient_context" not in payload


def test_generate_normalized_data():
    backend, mock_rest_client, _ = _make_backend()
    mock_rest_client.generate_normalized_data.return_value = {
        "conditions": [
            {
                "display": "Headache",
                "clinical_status": "active",
                "coding": [{"system": "ICD-10", "code": "R51", "display": "Headache"}],
            },
        ],
        "observations": [
            {
                "display": "Blood Pressure",
                "value": "120/80",
                "unit": "mmHg",
                "coding": [{"system": "LOINC", "code": "85354-9", "display": "Blood pressure"}],
            },
        ],
    }

    note = ClinicalNote(
        title="SOAP Note",
        sections=[NoteSection(key="subjective", title="Subjective", text="headache")],
    )
    result = backend.generate_normalized_data(note)

    assert isinstance(result, NormalizedData)
    assert len(result.conditions) == 1
    assert result.conditions[0].display == "Headache"
    assert result.conditions[0].clinical_status == "active"
    assert result.conditions[0].coding[0].code == "R51"
    assert len(result.observations) == 1
    assert result.observations[0].value == "120/80"
    assert result.observations[0].coding[0].system == "LOINC"

    payload = mock_rest_client.generate_normalized_data.call_args.args[0]
    assert payload["note"]["title"] == "SOAP Note"
    assert len(payload["note"]["sections"]) == 1


def test_parse_note_empty():
    result = NablaBackend._parse_note({})
    assert isinstance(result, ClinicalNote)
    assert result.title == ""
    assert result.sections == []


def test_parse_normalized_data_empty():
    result = NablaBackend._parse_normalized_data({})
    assert isinstance(result, NormalizedData)
    assert result.conditions == []
    assert result.observations == []
