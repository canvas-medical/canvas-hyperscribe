import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from django.db.models import QuerySet

from canvas_sdk.effects.simple_api import JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin

from hyperscribe.scribe.api.session_view import (
    SUMMARY_STEPS,
    ScribeSessionView,
    _CACHE_KEY_PREFIX,
    _PROGRESS_CACHE_KEY_PREFIX,
    _SUMMARY_CACHE_KEY_PREFIX,
    _match_conditions_to_sections,
)
from hyperscribe.scribe.backend import ScribeError
from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    CodingEntry,
    CommandProposal,
    Condition,
    NormalizedData,
    NoteSection,
    Observation,
)

# Disable automatic route resolution
ScribeSessionView._ROUTES = {}


def _helper_instance(staff_id: str = "staff-key-abc") -> ScribeSessionView:
    event = SimpleNamespace(context={"method": "GET"})
    secrets: dict[str, str] = {"ScribeBackend": '{"vendor": "nabla", "client_id": "id", "client_secret": "secret"}'}
    environment: dict[str, str] = {}
    view = ScribeSessionView(event, secrets, environment)
    view._path_pattern = re.compile(r".*")
    view.request = SimpleNamespace(
        headers={"canvas-logged-in-user-id": staff_id},
        query_params={},
        body=b"",
    )
    return view


def test_class() -> None:
    assert issubclass(ScribeSessionView, StaffSessionAuthMixin)
    assert issubclass(ScribeSessionView, SimpleAPI)


def test_constants() -> None:
    assert ScribeSessionView.PREFIX == "/scribe-session"


# --- /config ---


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_success(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.get_transcription_config.return_value = {
        "vendor": "nabla",
        "ws_url": "wss://example.com/ws",
        "access_token": "tok",
        "sample_rate": 16000,
    }
    get_backend.return_value = mock_backend

    view = _helper_instance(staff_id="staff-key-abc")
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
def test_get_config_unknown_vendor(get_backend: MagicMock) -> None:
    get_backend.side_effect = ScribeError("Unknown scribe vendor: 'bad'")

    view = _helper_instance()
    result = view.get_config()

    expected = [JSONResponse({"error": "Unknown scribe vendor: 'bad'"}, status_code=HTTPStatus.BAD_REQUEST)]
    assert result == expected


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_get_config_auth_error(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.get_transcription_config.side_effect = ScribeError("Auth failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    result = view.get_config()

    expected = [JSONResponse({"error": "Auth failed"}, status_code=HTTPStatus.INTERNAL_SERVER_ERROR)]
    assert result == expected


# --- /transcript ---


def _mock_cache() -> MagicMock:
    """Create a dict-backed mock cache."""
    store: dict[str, str] = {}
    cache = MagicMock()
    cache.set = lambda key, value, **kw: store.__setitem__(key, value)
    cache.get = lambda key, default=None: store.get(key, default)
    cache.delete = lambda key: store.pop(key, None)
    cache._store = store
    return cache


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_transcript_success(mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    items = [{"text": "Hello", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 1000}]
    cache._store[f"{_CACHE_KEY_PREFIX}55"] = json.dumps({"items": items, "finalized": True})

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "55"})
    result = view.get_transcript()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"items": items, "finalized": True}


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_transcript_empty(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "999"})
    result = view.get_transcript()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"items": [], "finalized": False}


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_transcript_missing_note_id(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_transcript()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST


# --- /save-transcript ---


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_save_transcript_success(mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache

    view = _helper_instance()
    items = [{"text": "Hello", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 1000}]
    view.request = SimpleNamespace(body=json.dumps({"note_id": "42", "transcript": {"items": items}}))
    result = view.post_save_transcript()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"status": "ok"}
    assert json.loads(cache._store[f"{_CACHE_KEY_PREFIX}42"]) == {"items": items, "finalized": False}


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_save_transcript_missing_note_id(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"transcript": {"items": []}}))
    result = view.post_save_transcript()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_id" in json.loads(result[0].content)["error"]


def test_save_transcript_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_save_transcript()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


# --- /summary ---


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_summary_success(mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    summary_data = {
        "note": {"title": "SOAP", "sections": [{"key": "cc", "title": "CC", "text": "Pain"}]},
        "commands": [{"command_type": "rfv", "data": {"comment": "Pain"}}],
        "approved": True,
    }
    cache._store[f"{_SUMMARY_CACHE_KEY_PREFIX}55"] = json.dumps(summary_data)

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "55"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == summary_data


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_summary_empty(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "999"})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"note": None, "commands": [], "approved": False}


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_summary_missing_note_id(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST


# --- /save-summary ---


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_save_summary_success(mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache

    view = _helper_instance()
    note = {"title": "SOAP", "sections": []}
    commands = [{"command_type": "hpi", "data": {"narrative": "Pain"}}]
    view.request = SimpleNamespace(
        body=json.dumps({"note_id": "42", "note": note, "commands": commands, "approved": True})
    )
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"status": "ok"}
    stored = json.loads(cache._store[f"{_SUMMARY_CACHE_KEY_PREFIX}42"])
    assert stored == {"note": note, "commands": commands, "approved": True}


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_save_summary_missing_note_id(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note": {}, "commands": []}))
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_id" in json.loads(result[0].content)["error"]


def test_save_summary_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_save_summary_defaults(mock_get_cache: MagicMock) -> None:
    """When approved is not provided, it defaults to False."""
    cache = _mock_cache()
    mock_get_cache.return_value = cache

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "10", "note": {}, "commands": []}))
    result = view.post_save_summary()

    assert result[0].status_code == HTTPStatus.OK
    stored = json.loads(cache._store[f"{_SUMMARY_CACHE_KEY_PREFIX}10"])
    assert stored["approved"] is False


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


@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_from_cache(get_backend: MagicMock, mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    cached_items = [{"text": "I feel dizzy", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 1500}]
    cache._store[f"{_CACHE_KEY_PREFIX}99"] = json.dumps({"items": cached_items, "finalized": True})

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[NoteSection(key="subjective", title="Subjective", text="Dizzy.")],
    )
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "99"}))
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.OK
    mock_backend.generate_note.assert_called_once()
    transcript_arg = mock_backend.generate_note.call_args.args[0]
    assert len(transcript_arg.items) == 1
    assert transcript_arg.items[0].text == "I feel dizzy"


@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_no_transcript_no_cache(get_backend: MagicMock, mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "999"}))
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "No transcript" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_rejects_non_finalized_transcript(get_backend: MagicMock, mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    cache._store[f"{_CACHE_KEY_PREFIX}42"] = json.dumps(
        {"items": [{"text": "hi", "speaker": "patient"}], "finalized": False}
    )
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "42"}))
    result = view.post_generate_note()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "still in progress" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_note_with_patient_context(get_backend: MagicMock) -> None:
    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(title="Note", sections=[])
    get_backend.return_value = mock_backend

    view = _helper_instance()
    item = {"text": "hi", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 500}
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "transcript": {"items": [item]},
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
    item = {"text": "hi", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 500}
    view.request = SimpleNamespace(body=json.dumps({"transcript": {"items": [item]}}))
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
    # section_conditions: "subjective" mentions "Headache"
    assert "section_conditions" in response_data
    assert "subjective" in response_data["section_conditions"]
    assert response_data["section_conditions"]["subjective"][0]["display"] == "Headache"


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


# --- _match_conditions_to_sections ---


def test_match_conditions_assessment_plan_gets_all() -> None:
    """Assessment/plan sections receive all conditions regardless of text."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="assessment_and_plan", title="A&P", text="Manage conditions."),
            NoteSection(key="plan", title="Plan", text="Follow up."),
        ],
    )
    headache_coding = [CodingEntry(system="ICD-10", code="R51", display="Headache")]
    htn_coding = [CodingEntry(system="ICD-10", code="I10", display="Essential hypertension")]
    conditions = [
        Condition(display="Headache", clinical_status="active", coding=headache_coding),
        Condition(display="Hypertension", clinical_status="active", coding=htn_coding),
    ]
    result = _match_conditions_to_sections(note, conditions)
    assert len(result["assessment_and_plan"]) == 2
    assert len(result["plan"]) == 2


def test_match_conditions_text_match() -> None:
    """Non-plan sections only get conditions whose display matches the text."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="history_of_present_illness", title="HPI", text="Patient reports a headache for 3 days."),
        ],
    )
    headache_coding = [CodingEntry(system="ICD-10", code="R51", display="Headache")]
    htn_coding = [CodingEntry(system="ICD-10", code="I10", display="Essential hypertension")]
    conditions = [
        Condition(display="Headache", clinical_status="active", coding=headache_coding),
        Condition(display="Hypertension", clinical_status="active", coding=htn_coding),
    ]
    result = _match_conditions_to_sections(note, conditions)
    assert len(result["history_of_present_illness"]) == 1
    assert result["history_of_present_illness"][0]["display"] == "Headache"
    assert result["history_of_present_illness"][0]["coding"][0]["code"] == "R51"


def test_match_conditions_case_insensitive() -> None:
    """Matching is case-insensitive."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="subjective", title="Subjective", text="SEVERE HEADACHE reported.")],
    )
    conditions = [
        Condition(display="headache", clinical_status="active", coding=[]),
    ]
    result = _match_conditions_to_sections(note, conditions)
    assert "subjective" in result
    assert result["subjective"][0]["display"] == "headache"


def test_match_conditions_empty_section_text() -> None:
    """Sections with empty text produce no entries (unless assessment/plan)."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="review_of_systems", title="ROS", text="")],
    )
    conditions = [
        Condition(display="Headache", clinical_status="active", coding=[]),
    ]
    result = _match_conditions_to_sections(note, conditions)
    assert "review_of_systems" not in result


def test_match_conditions_no_conditions() -> None:
    """When there are no conditions, all sections produce empty result."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="assessment_and_plan", title="A&P", text="Plan here."),
            NoteSection(key="subjective", title="Subjective", text="Pain."),
        ],
    )
    result = _match_conditions_to_sections(note, [])
    assert result == {}


# --- /extract-commands ---


def test_extract_commands_success() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [
                        {"key": "chief_complaint", "title": "Chief Complaint", "text": "Back pain for 3 weeks."},
                        {"key": "history_of_present_illness", "title": "HPI", "text": "Radiates to left leg."},
                        {"key": "vitals", "title": "Vitals", "text": "BP 120/80, HR 72"},
                        {"key": "plan", "title": "Plan", "text": "Start naproxen. Order MRI."},
                    ],
                }
            }
        )
    )
    result = view.post_extract_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    commands = data["commands"]
    types = [c["command_type"] for c in commands]
    assert types == ["rfv", "hpi", "vitals", "plan"]
    assert commands[0]["data"]["comment"] == "Back pain for 3 weeks."
    assert commands[0]["section_key"] == "chief_complaint"
    assert commands[1]["data"]["narrative"] == "Radiates to left leg."
    assert commands[1]["section_key"] == "history_of_present_illness"
    assert commands[2]["data"]["blood_pressure_systole"] == 120
    assert commands[2]["data"]["pulse"] == 72
    assert commands[2]["section_key"] == "vitals"
    assert commands[3]["data"]["narrative"] == "Start naproxen. Order MRI."
    assert commands[3]["section_key"] == "plan"
    assert all(c["selected"] is True for c in commands)
    assert all(c["already_documented"] is False for c in commands)


def test_extract_commands_empty_note() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Empty", "sections": []}}))
    result = view.post_extract_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["commands"] == []


def test_extract_commands_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_extract_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


# --- /insert-commands ---


@patch("hyperscribe.scribe.api.session_view.build_effects")
def test_insert_commands_success(mock_build: MagicMock) -> None:
    mock_effect_1 = MagicMock()
    mock_effect_2 = MagicMock()
    mock_build.return_value = [mock_effect_1, mock_effect_2]

    view = _helper_instance()
    commands = [
        {"command_type": "hpi", "data": {"narrative": "Back pain"}},
        {"command_type": "plan", "data": {"narrative": "Start naproxen"}},
    ]
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": commands}))
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["inserted"] == 2
    assert len(result) == 3  # JSONResponse + 2 effects
    assert result[1] is mock_effect_1
    assert result[2] is mock_effect_2
    mock_build.assert_called_once_with(commands, "note-uuid-123")


@patch("hyperscribe.scribe.api.session_view.build_effects")
def test_insert_commands_empty(mock_build: MagicMock) -> None:
    mock_build.return_value = []

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_uuid": "note-uuid-123", "commands": []}))
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["inserted"] == 0
    assert len(result) == 1


def test_insert_commands_missing_note_uuid() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"commands": []}))
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_uuid" in json.loads(result[0].content)["error"]


def test_insert_commands_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_insert_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


# --- annotate_duplicates delegation ---


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
def test_extract_commands_with_note_uuid_triggers_annotation(mock_annotate: MagicMock) -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [{"key": "chief_complaint", "title": "CC", "text": "Pain."}],
                },
                "note_uuid": "note-uuid-123",
            }
        )
    )
    view.post_extract_commands()
    mock_annotate.assert_called_once()
    assert mock_annotate.call_args.args[1] == "note-uuid-123"


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
def test_extract_commands_without_note_uuid_calls_annotate_with_empty(mock_annotate: MagicMock) -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [{"key": "chief_complaint", "title": "CC", "text": "Pain."}],
                },
            }
        )
    )
    view.post_extract_commands()
    mock_annotate.assert_called_once()
    assert mock_annotate.call_args.args[1] == ""


# --- /search-medications ---


@patch("hyperscribe.scribe.api.session_view.CanvasScience.medication_details")
def test_search_medications_success(mock_details: MagicMock) -> None:
    from hyperscribe.structures.medication_detail import MedicationDetail

    mock_details.return_value = [
        MedicationDetail(fdb_code="12345", description="Lisinopril 10mg Tablet", quantities=[]),
        MedicationDetail(fdb_code="67890", description="Lisinopril 20mg Tablet", quantities=[]),
    ]
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "Lisinopril"})
    result = view.get_search_medications()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert len(data["results"]) == 2
    assert data["results"][0]["fdb_code"] == "12345"
    assert data["results"][0]["description"] == "Lisinopril 10mg Tablet"
    assert data["results"][0]["quantities"] == []
    mock_details.assert_called_once_with(["Lisinopril"])


@patch("hyperscribe.scribe.api.session_view.CanvasScience.medication_details")
def test_search_medications_no_results(mock_details: MagicMock) -> None:
    mock_details.return_value = []
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "xyznonexistent"})
    result = view.get_search_medications()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_medications_empty_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": ""})
    result = view.get_search_medications()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_medications_missing_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_search_medications()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


# --- /search-allergies ---


@patch("hyperscribe.scribe.api.session_view.CanvasScience.search_allergy")
def test_search_allergies_success(mock_search: MagicMock) -> None:
    from hyperscribe.structures.allergy_detail import AllergyDetail

    mock_search.return_value = [
        AllergyDetail(
            concept_id_value=100,
            concept_id_description="Penicillin",
            concept_type="Allergen Group",
            concept_id_type=1,
        ),
        AllergyDetail(
            concept_id_value=200,
            concept_id_description="Amoxicillin",
            concept_type="Medication",
            concept_id_type=2,
        ),
    ]
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "penicillin"})
    result = view.get_search_allergies()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert len(data["results"]) == 2
    assert data["results"][0]["concept_id"] == 100
    assert data["results"][0]["description"] == "Penicillin"
    assert data["results"][0]["concept_id_type"] == 1
    assert data["results"][1]["concept_id"] == 200
    mock_search.assert_called_once()


@patch("hyperscribe.scribe.api.session_view.CanvasScience.search_allergy")
def test_search_allergies_no_results(mock_search: MagicMock) -> None:
    mock_search.return_value = []
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": "xyznonexistent"})
    result = view.get_search_allergies()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_allergies_empty_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"query": ""})
    result = view.get_search_allergies()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


def test_search_allergies_missing_query() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(query_params={})
    result = view.get_search_allergies()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["results"] == []


# --- /assignees ---


@patch("hyperscribe.scribe.api.session_view.Team")
@patch("hyperscribe.scribe.api.session_view.Staff")
def test_get_assignees_success(mock_staff_cls: MagicMock, mock_team_cls: MagicMock) -> None:
    staff_qs = MagicMock(spec=QuerySet)
    staff_qs.order_by.return_value = MagicMock(spec=QuerySet)
    staff_qs.order_by.return_value.values.return_value = [
        {"dbid": 1, "first_name": "Jane", "last_name": "Doe"},
        {"dbid": 2, "first_name": "John", "last_name": "Smith"},
    ]
    mock_staff_cls.objects.filter.return_value = staff_qs

    team_qs = MagicMock(spec=QuerySet)
    team_qs.order_by.return_value = MagicMock(spec=QuerySet)
    team_qs.order_by.return_value.values.return_value = [
        {"dbid": 10, "name": "Nursing"},
    ]
    mock_team_cls.objects.all.return_value = team_qs

    view = _helper_instance()
    result = view.get_assignees()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assignees = data["assignees"]
    assert len(assignees) == 3
    assert assignees[0] == {"type": "staff", "id": 1, "label": "Jane Doe"}
    assert assignees[1] == {"type": "staff", "id": 2, "label": "John Smith"}
    assert assignees[2] == {"type": "team", "id": 10, "label": "Nursing"}


@patch("hyperscribe.scribe.api.session_view.Team")
@patch("hyperscribe.scribe.api.session_view.Staff")
def test_get_assignees_empty(mock_staff_cls: MagicMock, mock_team_cls: MagicMock) -> None:
    staff_qs = MagicMock(spec=QuerySet)
    staff_qs.order_by.return_value = MagicMock(spec=QuerySet)
    staff_qs.order_by.return_value.values.return_value = []
    mock_staff_cls.objects.filter.return_value = staff_qs

    team_qs = MagicMock(spec=QuerySet)
    team_qs.order_by.return_value = MagicMock(spec=QuerySet)
    team_qs.order_by.return_value.values.return_value = []
    mock_team_cls.objects.all.return_value = team_qs

    view = _helper_instance()
    result = view.get_assignees()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["assignees"] == []


# --- /recommend-commands ---


@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_success(mock_recommend: MagicMock) -> None:
    mock_recommend.return_value = [
        CommandProposal(
            command_type="medication_statement",
            display="Lisinopril 10mg",
            data={"medication_text": "Lisinopril 10mg", "fdb_code": None, "sig": "Take daily"},
            section_key="_recommended",
        ),
        CommandProposal(
            command_type="allergy",
            display="Penicillin",
            data={
                "allergy_text": "Penicillin",
                "concept_id": 100,
                "concept_id_type": 1,
                "reaction": "rash",
                "severity": "moderate",
            },
            section_key="_recommended",
        ),
    ]

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {
                    "title": "Note",
                    "sections": [
                        {"key": "current_medications", "title": "Current Medications", "text": "Lisinopril 10mg daily"},
                        {"key": "allergies", "title": "Allergies", "text": "Penicillin (rash)"},
                    ],
                },
            }
        )
    )
    result = view.post_recommend_commands()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert len(data["commands"]) == 2
    assert data["commands"][0]["command_type"] == "medication_statement"
    assert data["commands"][0]["section_key"] == "_recommended"
    assert data["commands"][1]["command_type"] == "allergy"
    mock_recommend.assert_called_once()


def test_recommend_commands_missing_api_key() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Note", "sections": []}}))
    result = view.post_recommend_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    data = json.loads(result[0].content)
    assert "AnthropicAPIKey" in data["error"]


def test_recommend_commands_invalid_json() -> None:
    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body="not-json")
    result = view.post_recommend_commands()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_backend_error(mock_recommend: MagicMock) -> None:
    mock_recommend.side_effect = Exception("LLM failure")

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Note", "sections": []}}))
    result = view.post_recommend_commands()

    assert result[0].status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    data = json.loads(result[0].content)
    assert "failed" in data["error"].lower()


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_with_note_uuid_triggers_annotation(
    mock_recommend: MagicMock,
    mock_annotate: MagicMock,
) -> None:
    mock_recommend.return_value = [
        CommandProposal(
            command_type="medication_statement",
            display="Lisinopril 10mg",
            data={"medication_text": "Lisinopril 10mg"},
            section_key="_recommended",
        ),
    ]

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(
        body=json.dumps(
            {
                "note": {"title": "Note", "sections": []},
                "note_uuid": "note-uuid-456",
            }
        )
    )
    view.post_recommend_commands()
    mock_annotate.assert_called_once()
    assert mock_annotate.call_args.args[1] == "note-uuid-456"


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
def test_recommend_commands_without_note_uuid_calls_annotate_with_empty(
    mock_recommend: MagicMock,
    mock_annotate: MagicMock,
) -> None:
    mock_recommend.return_value = []

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body=json.dumps({"note": {"title": "Note", "sections": []}}))
    view.post_recommend_commands()
    mock_annotate.assert_called_once()
    assert mock_annotate.call_args.args[1] == ""


# --- /summary-progress ---


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_summary_progress_found(mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    cache._store[f"{_PROGRESS_CACHE_KEY_PREFIX}42"] = json.dumps(
        {"step": 2, "total": 5, "label": "Extracting commands"}
    )

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "42"})
    result = view.get_summary_progress()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["step"] == 2
    assert data["total"] == 5
    assert data["label"] == "Extracting commands"


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_summary_progress_not_found(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "999"})
    result = view.get_summary_progress()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["step"] == -1


# --- /generate-summary ---


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.suggest_diagnoses")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_success(
    get_backend: MagicMock,
    mock_get_cache: MagicMock,
    mock_recommend: MagicMock,
    mock_suggest: MagicMock,
    _mock_annotate: MagicMock,
) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    # Seed finalized transcript.
    cache._store[f"{_CACHE_KEY_PREFIX}55"] = json.dumps(
        {
            "items": [{"text": "I have a headache", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 2000}],
            "finalized": True,
        }
    )

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="SOAP Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Headache."),
            NoteSection(
                key="assessment_and_plan",
                title="A&P",
                text="Migraine\n- Start sumatriptan",
            ),
        ],
    )
    mock_backend.generate_normalized_data.return_value = NormalizedData(
        conditions=[
            Condition(
                display="Migraine",
                clinical_status="active",
                coding=[CodingEntry(system="ICD-10", code="G43", display="Migraine")],
            )
        ],
        observations=[],
    )
    get_backend.return_value = mock_backend
    mock_recommend.return_value = [
        CommandProposal(
            command_type="medication_statement",
            display="Sumatriptan",
            data={"medication_text": "Sumatriptan"},
            section_key="_recommended",
        ),
    ]
    mock_suggest.return_value = {}

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body=json.dumps({"note_id": "55", "note_uuid": "55"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["note"]["title"] == "SOAP Note"
    assert len(data["commands"]) >= 1
    # Plan should have been split into diagnose commands.
    diagnose_cmds = [c for c in data["commands"] if c["command_type"] == "diagnose"]
    assert len(diagnose_cmds) == 1
    assert diagnose_cmds[0]["data"]["icd10_code"] == "G43"
    assert len(data["recommendations"]) == 1
    assert data["recommendations"][0]["command_type"] == "medication_statement"
    # Summary should be saved to cache.
    assert f"{_SUMMARY_CACHE_KEY_PREFIX}55" in cache._store


@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_missing_note_id(get_backend: MagicMock, mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "note_id" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_no_transcript(get_backend: MagicMock, mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()
    get_backend.return_value = MagicMock()

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "99"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "No transcript" in json.loads(result[0].content)["error"]


def test_generate_summary_invalid_json() -> None:
    view = _helper_instance()
    view.request = SimpleNamespace(body="not-json")
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.BAD_REQUEST
    assert "Invalid JSON" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_backend_error(get_backend: MagicMock, mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    cache._store[f"{_CACHE_KEY_PREFIX}42"] = json.dumps(
        {"items": [{"text": "hi", "speaker": "patient"}], "finalized": True}
    )

    mock_backend = MagicMock()
    mock_backend.generate_note.side_effect = ScribeError("Note generation failed")
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "42"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert "Note generation failed" in json.loads(result[0].content)["error"]


@patch("hyperscribe.scribe.api.session_view.annotate_duplicates")
@patch("hyperscribe.scribe.api.session_view.recommend_commands")
@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_non_critical_failures(
    get_backend: MagicMock,
    mock_get_cache: MagicMock,
    mock_recommend: MagicMock,
    _mock_annotate: MagicMock,
) -> None:
    """When non-critical steps fail, the response still includes what succeeded."""
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    cache._store[f"{_CACHE_KEY_PREFIX}77"] = json.dumps(
        {"items": [{"text": "hi", "speaker": "patient"}], "finalized": True}
    )

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(
        title="Note", sections=[NoteSection(key="chief_complaint", title="CC", text="Pain.")]
    )
    mock_backend.generate_normalized_data.side_effect = Exception("Normalized data failed")
    get_backend.return_value = mock_backend
    mock_recommend.side_effect = Exception("Recommend failed")

    view = _helper_instance()
    view.secrets["AnthropicAPIKey"] = "test-key"
    view.request = SimpleNamespace(body=json.dumps({"note_id": "77", "note_uuid": "77"}))
    result = view.post_generate_summary()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["note"]["title"] == "Note"
    assert len(data["commands"]) >= 1
    assert data["recommendations"] == []
    assert data["diagnosis_suggestions"] == {}


@patch("hyperscribe.scribe.api.session_view.get_cache")
@patch("hyperscribe.scribe.api.session_view.get_backend_from_secrets")
def test_generate_summary_writes_progress(get_backend: MagicMock, mock_get_cache: MagicMock) -> None:
    """Progress cache is updated during the pipeline."""
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    cache._store[f"{_CACHE_KEY_PREFIX}88"] = json.dumps(
        {"items": [{"text": "test", "speaker": "patient"}], "finalized": True}
    )

    mock_backend = MagicMock()
    mock_backend.generate_note.return_value = ClinicalNote(title="Note", sections=[])
    mock_backend.generate_normalized_data.return_value = NormalizedData(conditions=[], observations=[])
    get_backend.return_value = mock_backend

    view = _helper_instance()
    view.request = SimpleNamespace(body=json.dumps({"note_id": "88"}))
    view.post_generate_summary()

    # After completion, progress cache should have the last step written.
    progress_key = f"{_PROGRESS_CACHE_KEY_PREFIX}88"
    assert progress_key in cache._store
    progress = json.loads(cache._store[progress_key])
    assert progress["step"] == len(SUMMARY_STEPS) - 1
    assert progress["total"] == len(SUMMARY_STEPS)
