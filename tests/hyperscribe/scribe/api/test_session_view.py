import json
import re
from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from canvas_sdk.effects.simple_api import JSONResponse
from canvas_sdk.handlers.simple_api import SimpleAPI, StaffSessionAuthMixin

from hyperscribe.scribe.api.session_view import (
    ScribeSessionView,
    _CACHE_KEY_PREFIX,
    _annotate_medication_duplicates,
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
    view._staff_id = staff_id
    return view


def test_class() -> None:
    assert issubclass(ScribeSessionView, StaffSessionAuthMixin)
    assert issubclass(ScribeSessionView, SimpleAPI)


def test_constants() -> None:
    assert ScribeSessionView.PREFIX == "/scribe-session"


def test_authenticate() -> None:
    view = _helper_instance()
    credentials = SimpleNamespace(logged_in_user={"id": "staff-123", "type": "Staff"})
    # StaffSessionAuthMixin.authenticate checks type == "Staff"
    with patch.object(StaffSessionAuthMixin, "authenticate", return_value=True):
        result = view.authenticate(credentials)  # type: ignore[arg-type]
    assert result is True
    assert view._staff_id == "staff-123"


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
    cache._store = store
    return cache


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_transcript_success(mock_get_cache: MagicMock) -> None:
    cache = _mock_cache()
    mock_get_cache.return_value = cache
    items = [{"text": "Hello", "speaker": "patient", "start_offset_ms": 0, "end_offset_ms": 1000}]
    cache._store[f"{_CACHE_KEY_PREFIX}55"] = json.dumps(items)

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "55"})
    result = view.get_transcript()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"items": items}


@patch("hyperscribe.scribe.api.session_view.get_cache")
def test_get_transcript_empty(mock_get_cache: MagicMock) -> None:
    mock_get_cache.return_value = _mock_cache()

    view = _helper_instance()
    view.request = SimpleNamespace(query_params={"note_id": "999"})
    result = view.get_transcript()

    assert result[0].status_code == HTTPStatus.OK
    assert json.loads(result[0].content) == {"items": []}


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
    assert json.loads(cache._store[f"{_CACHE_KEY_PREFIX}42"]) == items


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
    cache._store[f"{_CACHE_KEY_PREFIX}99"] = json.dumps(cached_items)

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


# --- _annotate_medication_duplicates ---


@patch("hyperscribe.scribe.api.session_view.MedicationCoding")
@patch("hyperscribe.scribe.api.session_view.Medication")
@patch("hyperscribe.scribe.api.session_view.Note")
def test_annotate_medication_duplicates_match(
    mock_note_cls: MagicMock,
    mock_med_cls: MagicMock,
    mock_coding_cls: MagicMock,
) -> None:
    mock_patient = MagicMock()
    mock_patient.id = "patient-key"
    mock_note = MagicMock()
    mock_note.patient = mock_patient
    mock_note_cls.objects.select_related.return_value.get.return_value = mock_note

    mock_med_qs = MagicMock()
    mock_med_cls.objects.for_patient.return_value.filter.return_value = mock_med_qs

    mock_coding = MagicMock()
    mock_coding.display = "Lisinopril 10mg Tablet"
    mock_coding_cls.objects.filter.return_value = [mock_coding]

    med_data_1 = {"medication_text": "Lisinopril 10mg"}
    med_data_2 = {"medication_text": "Metformin 500mg"}
    proposals = [
        CommandProposal(
            command_type="medication_statement",
            display="Lisinopril 10mg",
            data=med_data_1,
        ),
        CommandProposal(
            command_type="medication_statement",
            display="Metformin 500mg",
            data=med_data_2,
        ),
        CommandProposal(command_type="hpi", display="Pain", data={"narrative": "Pain"}),
    ]
    _annotate_medication_duplicates(proposals, "note-uuid")

    assert proposals[0].already_documented is True  # substring match
    assert proposals[1].already_documented is False
    assert proposals[2].already_documented is False  # non-medication untouched


@patch("hyperscribe.scribe.api.session_view.Note")
def test_annotate_medication_duplicates_note_not_found(mock_note_cls: MagicMock) -> None:
    # Set DoesNotExist to a real exception class so `except Note.DoesNotExist` works
    mock_note_cls.DoesNotExist = type("DoesNotExist", (Exception,), {})
    mock_note_cls.objects.select_related.return_value.get.side_effect = mock_note_cls.DoesNotExist

    proposals = [
        CommandProposal(
            command_type="medication_statement",
            display="Lisinopril",
            data={"medication_text": "Lisinopril"},
        ),
    ]
    _annotate_medication_duplicates(proposals, "nonexistent-uuid")
    assert proposals[0].already_documented is False


def test_annotate_medication_duplicates_no_medications() -> None:
    proposals = [
        CommandProposal(command_type="hpi", display="Pain", data={"narrative": "Pain"}),
    ]
    _annotate_medication_duplicates(proposals, "note-uuid")
    assert proposals[0].already_documented is False


@patch("hyperscribe.scribe.api.session_view._annotate_medication_duplicates")
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


@patch("hyperscribe.scribe.api.session_view._annotate_medication_duplicates")
def test_extract_commands_without_note_uuid_skips_annotation(mock_annotate: MagicMock) -> None:
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
    mock_annotate.assert_not_called()


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


# --- /assignees ---


@patch("hyperscribe.scribe.api.session_view.Team")
@patch("hyperscribe.scribe.api.session_view.Staff")
def test_get_assignees_success(mock_staff_cls: MagicMock, mock_team_cls: MagicMock) -> None:
    mock_staff_cls.objects.filter.return_value.order_by.return_value.values.return_value = [
        {"dbid": 1, "first_name": "Jane", "last_name": "Doe"},
        {"dbid": 2, "first_name": "John", "last_name": "Smith"},
    ]
    mock_team_cls.objects.all.return_value.order_by.return_value.values.return_value = [
        {"dbid": 10, "name": "Nursing"},
    ]

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
    mock_staff_cls.objects.filter.return_value.order_by.return_value.values.return_value = []
    mock_team_cls.objects.all.return_value.order_by.return_value.values.return_value = []

    view = _helper_instance()
    result = view.get_assignees()

    assert result[0].status_code == HTTPStatus.OK
    data = json.loads(result[0].content)
    assert data["assignees"] == []
