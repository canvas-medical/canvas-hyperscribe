from unittest.mock import patch

from hyperscribe.scribe.base import ScribeBackend
from hyperscribe.scribe.models import (
    AsyncJob,
    ClinicalNote,
    CodingEntry,
    NormalizedData,
    NoteSection,
    PatientContext,
    Transcript,
    TranscriptItem,
    TranscriptionStatus,
)
from hyperscribe.scribe.nabla.backend import NablaBackend


def _make_backend():
    with patch("hyperscribe.scribe.nabla.backend.NablaAuth"):
        with patch("hyperscribe.scribe.nabla.backend.NablaClient") as mock_client_cls:
            backend = NablaBackend(region="us", client_id="cid", client_secret="secret")
            mock_client = mock_client_cls.return_value
    return backend, mock_client


def test_nabla_backend_is_scribe_backend():
    backend, _ = _make_backend()
    assert isinstance(backend, ScribeBackend)


def test_transcribe():
    backend, mock_client = _make_backend()
    mock_client.transcribe_sync.return_value = {
        "items": [
            {
                "text": "I have a headache",
                "speaker": "patient",
                "start_offset_ms": 0,
                "end_offset_ms": 2000,
            },
            {
                "text": "How long?",
                "speaker": "practitioner",
                "start_offset_ms": 2100,
                "end_offset_ms": 3000,
            },
        ],
    }

    result = backend.transcribe(b"audio")

    assert isinstance(result, Transcript)
    assert len(result.items) == 2
    assert result.items[0].text == "I have a headache"
    assert result.items[0].speaker == "patient"
    assert result.items[0].start_offset_ms == 0
    assert result.items[0].end_offset_ms == 2000
    assert result.items[1].speaker == "practitioner"

    params = mock_client.transcribe_sync.call_args.args[1]
    assert params == {"speech_locales": "en-US"}


def test_transcribe_async_start():
    backend, mock_client = _make_backend()
    mock_client.transcribe_async_start.return_value = {"id": "job-456"}

    job_id = backend.transcribe_async_start("http://example.com/audio.wav")

    assert job_id == "job-456"
    payload = mock_client.transcribe_async_start.call_args.args[0]
    assert payload["file_url"] == "http://example.com/audio.wav"
    assert payload["speech_locales"] == ["en-US"]


def test_transcribe_async_poll_ongoing():
    backend, mock_client = _make_backend()
    mock_client.transcribe_async_poll.return_value = {"id": "job-1", "status": "ongoing"}

    result = backend.transcribe_async_poll("job-1")
    assert isinstance(result, AsyncJob)
    assert result.id == "job-1"
    assert result.status == TranscriptionStatus.ONGOING


def test_transcribe_async_poll_failed():
    backend, mock_client = _make_backend()
    mock_client.transcribe_async_poll.return_value = {"id": "job-1", "status": "failed"}

    result = backend.transcribe_async_poll("job-1")
    assert isinstance(result, AsyncJob)
    assert result.status == TranscriptionStatus.FAILED


def test_transcribe_async_poll_succeeded():
    backend, mock_client = _make_backend()
    mock_client.transcribe_async_poll.return_value = {
        "id": "job-1",
        "status": "succeeded",
        "items": [{"text": "done", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 100}],
    }

    result = backend.transcribe_async_poll("job-1")
    assert isinstance(result, Transcript)
    assert len(result.items) == 1
    assert result.items[0].text == "done"


def test_generate_note():
    backend, mock_client = _make_backend()
    mock_client.generate_note.return_value = {
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

    payload = mock_client.generate_note.call_args.args[0]
    assert payload["note_template"] == "SOAP"
    assert payload["locale"] == "en-US"
    assert len(payload["transcript"]["items"]) == 1


def test_generate_note_with_patient_context():
    backend, mock_client = _make_backend()
    mock_client.generate_note.return_value = {"title": "Note", "sections": []}

    ctx = PatientContext(
        name="Jane Doe",
        birth_date="1990-05-15",
        gender="female",
        encounter_diagnoses=[CodingEntry(system="ICD-10", code="R51", display="Headache")],
    )
    backend.generate_note(Transcript(), patient_context=ctx)

    payload = mock_client.generate_note.call_args.args[0]
    assert payload["patient_context"]["name"] == "Jane Doe"
    assert payload["patient_context"]["encounter_diagnoses"][0]["code"] == "R51"


def test_generate_note_without_patient_context():
    backend, mock_client = _make_backend()
    mock_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_client.generate_note.call_args.args[0]
    assert "patient_context" not in payload


def test_generate_normalized_data():
    backend, mock_client = _make_backend()
    mock_client.generate_normalized_data.return_value = {
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

    payload = mock_client.generate_normalized_data.call_args.args[0]
    assert payload["note"]["title"] == "SOAP Note"
    assert len(payload["note"]["sections"]) == 1


def test_parse_transcript_empty():
    result = NablaBackend._parse_transcript({})
    assert isinstance(result, Transcript)
    assert result.items == []


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
