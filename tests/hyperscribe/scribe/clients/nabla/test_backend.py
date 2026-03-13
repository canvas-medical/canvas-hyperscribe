from unittest.mock import MagicMock, patch

from hyperscribe.scribe.backend import (
    ClinicalNote,
    CodingEntry,
    NormalizedData,
    NoteSection,
    PatientContext,
    ScribeBackend,
    Transcript,
    TranscriptItem,
)
from hyperscribe.scribe.clients.nabla.backend import NablaBackend


def _make_backend() -> tuple[NablaBackend, MagicMock]:
    with patch("hyperscribe.scribe.clients.nabla.backend.NablaAuth") as mock_auth_cls:
        with patch("hyperscribe.scribe.clients.nabla.backend.NablaClient") as mock_client_cls:
            mock_auth = mock_auth_cls.return_value
            mock_auth.base_url = "https://us.api.nabla.com"
            mock_auth.get_access_token.return_value = "test-backend-token"
            mock_auth.get_user_tokens.return_value = ("user-access-token", "user-refresh-token")
            backend = NablaBackend(client_id="cid", client_secret="secret")
            mock_rest_client = mock_client_cls.return_value
    return backend, mock_rest_client


def test_nabla_backend_is_scribe_backend() -> None:
    backend, _ = _make_backend()
    assert isinstance(backend, ScribeBackend)


def test_get_transcription_config() -> None:
    backend, _ = _make_backend()
    config = backend.get_transcription_config(user_external_id="staff-key")

    assert config["vendor"] == "nabla"
    assert config["ws_url"] == "wss://us.api.nabla.com/v1/core/user/transcribe-ws?nabla-api-version=2026-02-20"
    assert config["access_token"] == "user-access-token"
    assert config["refresh_token"] == "user-refresh-token"
    assert config["sample_rate"] == 16000
    assert config["encoding"] == "PCM_S16LE"
    assert config["speech_locales"] == ["ENGLISH_US"]
    assert config["stream_id"] == "stream1"


def test_get_transcription_config_calls_user_tokens() -> None:
    backend, _ = _make_backend()
    backend.get_transcription_config(user_external_id="staff-key")

    backend._auth.get_user_tokens.assert_called_once_with("staff-key")


def test_generate_note() -> None:
    backend, mock_rest_client = _make_backend()
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
    assert payload["note_template"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
    assert payload["note_locale"] == "ENGLISH_US"
    assert len(payload["transcript_items"]) == 1
    assert payload["transcript_items"][0]["speaker_type"] == "patient"


def test_generate_note_with_patient_context() -> None:
    backend, mock_rest_client = _make_backend()
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


def test_generate_note_without_patient_context() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert "patient_context" not in payload


def test_generate_normalized_data() -> None:
    backend, mock_rest_client = _make_backend()
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


def test_parse_note_empty() -> None:
    result = NablaBackend._parse_note({})
    assert isinstance(result, ClinicalNote)
    assert result.title == ""
    assert result.sections == []


def test_parse_note_nested() -> None:
    raw = {
        "note": {
            "title": "SOAP Note",
            "sections": [{"key": "subjective", "title": "Subjective", "text": "Headache."}],
        },
        "locale": "ENGLISH_US",
        "template": "GENERIC_SOAP",
    }
    result = NablaBackend._parse_note(raw)
    assert result.title == "SOAP Note"
    assert len(result.sections) == 1
    assert result.sections[0].key == "subjective"


def test_parse_note_splits_ros_from_hpi() -> None:
    raw = {
        "title": "Visit Note",
        "sections": [
            {
                "key": "history_of_present_illness",
                "title": "History of Present Illness",
                "text": ("Patient reports headache for 3 days.\n\nROS\nGeneral: No fever.\nHEENT: Photophobia noted."),
            },
        ],
    }
    result = NablaBackend._parse_note(raw)
    assert len(result.sections) == 2
    assert result.sections[0].key == "history_of_present_illness"
    assert result.sections[0].text == "Patient reports headache for 3 days."
    assert result.sections[1].key == "review_of_systems"
    assert result.sections[1].title == "Review of Systems"
    assert "General: No fever." in result.sections[1].text
    assert "HEENT: Photophobia noted." in result.sections[1].text


def test_parse_note_splits_ros_full_phrase() -> None:
    raw = {
        "title": "Note",
        "sections": [
            {
                "key": "history_of_present_illness",
                "title": "HPI",
                "text": "Onset yesterday.\n\nReview of Systems\nSkin: No rash.",
            },
        ],
    }
    result = NablaBackend._parse_note(raw)
    assert len(result.sections) == 2
    assert result.sections[0].text == "Onset yesterday."
    assert result.sections[1].key == "review_of_systems"
    assert "Skin: No rash." in result.sections[1].text


def test_parse_note_splits_ros_bullet_with_colon() -> None:
    """ROS marker as a bullet point with trailing colon should be detected."""
    raw = {
        "title": "Note",
        "sections": [
            {
                "key": "history_of_present_illness",
                "title": "HPI",
                "text": (
                    "- Burning sensation during urination\n"
                    "- Denies rash\n"
                    "- Review of systems:\n"
                    "  - General: Sleeping well\n"
                    "  - Skin: Denies rash"
                ),
            },
        ],
    }
    result = NablaBackend._parse_note(raw)
    assert len(result.sections) == 2
    assert result.sections[0].key == "history_of_present_illness"
    assert "Burning sensation" in result.sections[0].text
    assert "Review of systems" not in result.sections[0].text
    assert result.sections[1].key == "review_of_systems"
    assert "General: Sleeping well" in result.sections[1].text


def test_parse_note_splits_ros_parenthetical_label() -> None:
    """'Review of Systems (ROS):' paragraph-style marker should be detected."""
    raw = {
        "title": "Note",
        "sections": [
            {
                "key": "history_of_present_illness",
                "title": "HPI",
                "text": (
                    "Patient is a 78-year-old female presenting with urinary symptoms.\n"
                    "\n"
                    "Review of Systems (ROS):\n"
                    "General: Afebrile, eating well.\n"
                    "Genitourinary: Improved bladder control."
                ),
            },
        ],
    }
    result = NablaBackend._parse_note(raw)
    assert len(result.sections) == 2
    assert result.sections[0].key == "history_of_present_illness"
    assert "78-year-old female" in result.sections[0].text
    assert "Review of Systems" not in result.sections[0].text
    assert result.sections[1].key == "review_of_systems"
    assert "General: Afebrile" in result.sections[1].text
    assert "Genitourinary: Improved" in result.sections[1].text


def test_parse_note_no_ros_in_hpi() -> None:
    raw = {
        "title": "Note",
        "sections": [
            {
                "key": "history_of_present_illness",
                "title": "HPI",
                "text": "Patient feeling well. No complaints.",
            },
        ],
    }
    result = NablaBackend._parse_note(raw)
    assert len(result.sections) == 1
    assert result.sections[0].key == "history_of_present_illness"
    assert result.sections[0].text == "Patient feeling well. No complaints."


def test_parse_note_ros_not_split_from_other_sections() -> None:
    """ROS marker in non-HPI sections should not be split."""
    raw = {
        "title": "Note",
        "sections": [
            {
                "key": "chief_complaint",
                "title": "CC",
                "text": "Headache.\nROS\nGeneral: Fatigue.",
            },
        ],
    }
    result = NablaBackend._parse_note(raw)
    assert len(result.sections) == 1
    assert result.sections[0].key == "chief_complaint"


def test_parse_normalized_data_empty() -> None:
    result = NablaBackend._parse_normalized_data({})
    assert isinstance(result, NormalizedData)
    assert result.conditions == []
    assert result.observations == []
