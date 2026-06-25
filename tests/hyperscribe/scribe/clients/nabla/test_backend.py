from typing import Any
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.backend import (
    ClinicalNote,
    CodingEntry,
    NormalizedData,
    NoteSection,
    PatientContext,
    ScribeBackend,
    ScribeError,
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
    assert config["ws_url"] == "wss://us.api.nabla.com/v1/core/user/transcribe-ws?nabla-api-version=2026-06-12"
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
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
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
    demographics = payload["structured_context"]["patient_demographics"]
    assert demographics["name"] == "Jane Doe"
    assert demographics["birth_date"] == "1990-05-15"
    assert demographics["gender"] == "FEMALE"
    assert "Jane Doe" in payload["note_sections_customization"][1]["custom_instruction"]


def test_generate_note_hpi_ros_instruction() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_rest_client.generate_note.call_args.args[0]
    hpi = next(
        e for e in payload["note_sections_customization"] if e.get("section_key") == "HISTORY_OF_PRESENT_ILLNESS"
    )
    instruction = hpi["custom_instruction"]

    # Combined HPI+ROS instruction must stay within Nabla's 700-character limit.
    assert len(instruction) <= 700, f"HPI/ROS instruction is {len(instruction)} chars (>700)"

    # HPI: full-sentence narrative with a clear subject, and no duplicate demographic
    # intro (the opener already states name/age, so the narrative must not restate them).
    assert "Open with one sentence in this exact format:" in instruction
    assert "clear subject" in instruction
    assert "do not restate the name or age" in instruction

    # ROS: Nabla picks the systems (no fixed list), but the parseable format is pinned —
    # the standalone "ROS" marker (_split_ros) and 1-3 word "System: findings" rows
    # (parse_ros_subsections).
    assert "you choose them" in instruction
    assert 'a line containing only "ROS"' in instruction
    assert '"System: findings"' in instruction
    assert "1-3 word name" in instruction
    assert "Never exceed three words." in instruction

    # The old hard-coded ROS system scaffold is gone.
    assert "Musculoskeletal:" not in instruction


def test_generate_note_with_unknown_gender_omits_field() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    ctx = PatientContext(name="Pat Smith", birth_date="1985-01-01", gender="UNK")
    backend.generate_note(Transcript(), patient_context=ctx)

    payload = mock_rest_client.generate_note.call_args.args[0]
    demographics = payload["structured_context"]["patient_demographics"]
    assert "gender" not in demographics


def test_generate_note_without_patient_context() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert "structured_context" not in payload


def test_generate_note_physical_exam_excludes_vitals() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_rest_client.generate_note.call_args.args[0]
    pe_entries = [
        entry for entry in payload["note_sections_customization"] if entry.get("section_key") == "PHYSICAL_EXAM"
    ]
    assert len(pe_entries) == 1, "expected exactly one PHYSICAL_EXAM customization entry"
    pe_entry = pe_entries[0]

    instruction = pe_entry["custom_instruction"]
    instruction_lower = instruction.lower()

    # The four vital signs called out in the requirement, each in long form and
    # in its common abbreviation/synonym, so the prompt blocks paraphrased leaks.
    required_terms = (
        "heart rate",
        "pulse",
        "hr",
        "blood pressure",
        "bp",
        "oxygen saturation",
        "spo2",
        "breaths per minute",
        "respiratory rate",
        "rr",
    )
    for term in required_terms:
        assert term in instruction_lower, f"missing exclusion term {term!r}"

    # Hard-imperative phrasing rather than a soft suggestion.
    assert "do not" in instruction_lower or "exclude" in instruction_lower

    # Names the destination section so the model has somewhere to put the data.
    assert "vitals section" in instruction_lower


def _section_entry(payload: dict, section_key: str) -> dict:
    entries = [e for e in payload["note_sections_customization"] if e.get("section_key") == section_key]
    assert len(entries) == 1, f"expected exactly one {section_key} customization entry"
    return entries[0]


def test_generate_note_hpi_uses_detailed_level_of_detail() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_rest_client.generate_note.call_args.args[0]
    hpi_entry = _section_entry(payload, "HISTORY_OF_PRESENT_ILLNESS")
    assert hpi_entry["level_of_detail"] == "DETAILED"


def test_generate_note_social_history_instruction() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_rest_client.generate_note.call_args.args[0]
    instruction = _section_entry(payload, "SOCIAL_HISTORY")["custom_instruction"]
    lower = instruction.lower()

    # Old "be thorough / include all" filler-prone phrasing is gone.
    assert "be thorough" not in lower
    # Core guardrails of the validated rewrite.
    assert "patient's own social history" in instruction
    assert "only what is actually discussed" in instruction
    assert "caregiver, or a companion in the room" in instruction
    assert "never state that a topic was not discussed" in lower
    assert "leave this section empty" in instruction


def test_generate_note_family_history_instruction() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript())

    payload = mock_rest_client.generate_note.call_args.args[0]
    instruction = _section_entry(payload, "FAMILY_HISTORY")["custom_instruction"]
    lower = instruction.lower()

    assert "be thorough" not in lower
    assert "biological relatives" in instruction
    assert "omit rather than guess" in instruction
    # No-filler guardrail, quoted example phrasing preserved.
    assert "no other family history discussed." in instruction
    assert "if none is discussed, leave empty" in lower


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


# --- Psychiatry template matching (function-based per CLAUDE.md) ---
# The template name comes from the /visit-templates endpoint (server-controlled),
# so it's always exactly "Psychiatry" — no need for case-insensitive matching.


# --- template capability check (split_by_problem support) ---


def test_template_supports_option_string_list() -> None:
    """Section options as a plain string list, exact key match."""
    detail = {
        "sections": [
            {"key": "ASSESSMENT_AND_PLAN", "supported_customization_options": ["STYLE", "SPLIT_BY_PROBLEM"]},
        ]
    }
    assert NablaBackend._template_supports_option(detail, "ASSESSMENT_AND_PLAN", "split_by_problem") is True


def test_template_supports_option_tolerates_shape_variants() -> None:
    """Nested under 'template', section_key field, dict-shaped options, case/underscore drift."""
    detail = {
        "template": {
            "sections": [
                {
                    "section_key": "assessmentAndPlan",
                    "customization_options": [{"name": "splitByProblem"}, {"key": "style"}],
                }
            ]
        }
    }
    assert NablaBackend._template_supports_option(detail, "ASSESSMENT_AND_PLAN", "split_by_problem") is True


def test_template_supports_option_absent_returns_false() -> None:
    """Option not listed for the section → False (and unknown section → False)."""
    detail = {"sections": [{"key": "ASSESSMENT_AND_PLAN", "supported_customization_options": ["STYLE"]}]}
    assert NablaBackend._template_supports_option(detail, "ASSESSMENT_AND_PLAN", "split_by_problem") is False
    assert NablaBackend._template_supports_option(detail, "PHYSICAL_EXAM", "split_by_problem") is False


def test_supports_psychiatry_ap_split_by_problem_true() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.get_note_template.return_value = {
        "sections": [{"key": "ASSESSMENT_AND_PLAN", "supported_customization_options": ["SPLIT_BY_PROBLEM"]}]
    }
    assert backend.supports_psychiatry_ap_split_by_problem() is True
    # Queries the psych AP-merged template specifically.
    assert mock_rest_client.get_note_template.call_args.args[0] == "PSYCHIATRY_MULTIPLE_SECTIONS_AP_MERGED"


def test_supports_psychiatry_ap_split_by_problem_false_when_unsupported() -> None:
    backend, mock_rest_client = _make_backend()
    mock_rest_client.get_note_template.return_value = {
        "sections": [{"key": "ASSESSMENT_AND_PLAN", "supported_customization_options": ["STYLE"]}]
    }
    assert backend.supports_psychiatry_ap_split_by_problem() is False


def test_supports_psychiatry_ap_split_by_problem_false_on_lookup_error() -> None:
    """Best-effort: a failed template lookup returns False, never raises."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.get_note_template.side_effect = ScribeError("boom", status_code=500)
    assert backend.supports_psychiatry_ap_split_by_problem() is False


def test_psychiatry_selects_psychiatry_template() -> None:
    """The 'Psychiatry' visit template routes to PSYCHIATRY_MULTIPLE_SECTIONS_AP_MERGED
    (available since nabla-api-version 2026-06-12) and uses the same single
    ASSESSMENT_AND_PLAN + split_by_problem customization as generic visits, so the
    A&P parses through the shared path with no local re-merge.
    """
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
    backend.generate_note(Transcript(), visit_template_name="Psychiatry")
    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "PSYCHIATRY_MULTIPLE_SECTIONS_AP_MERGED"
    customization = {c["section_key"]: c for c in payload["note_sections_customization"]}
    assert "ASSESSMENT_AND_PLAN" in customization
    assert customization["ASSESSMENT_AND_PLAN"]["split_by_problem"] is True
    assert "ASSESSMENT" not in customization
    assert "PLAN" not in customization


def test_non_psychiatry_uses_generic() -> None:
    """A non-psychiatry template name routes to the generic Nabla template."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
    backend.generate_note(Transcript(), visit_template_name="Primary Care")
    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"


def test_physical_exam_instruction_requests_colon_delimited_systems() -> None:
    """The PHYSICAL_EXAM customization asks for "System: findings" rows so the exam
    parses into per-system subsections (parse_ros_subsections needs the colon;
    regression for colon-less PE collapsing into one block). The instruction is
    shared, so this must hold for BOTH the generic and psychiatry branches, and the
    original vitals-exclusion directive must be retained."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
    for visit_template_name in ("", "Psychiatry"):
        backend.generate_note(Transcript(), visit_template_name=visit_template_name)
        payload = mock_rest_client.generate_note.call_args.args[0]
        pe = next(c for c in payload["note_sections_customization"] if c["section_key"] == "PHYSICAL_EXAM")
        instruction = pe["custom_instruction"]
        assert "System: findings" in instruction, visit_template_name
        assert "vital signs belong in the Vitals section" in instruction, visit_template_name


def test_empty_name_uses_generic() -> None:
    """An empty visit_template_name routes to the generic Nabla template."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
    backend.generate_note(Transcript(), visit_template_name="")
    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"


def test_psychiatry_payload_has_mental_health_exam() -> None:
    """The psychiatry Nabla payload includes the MENTAL_HEALTH_EXAM section customization."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
    backend.generate_note(Transcript(), visit_template_name="Psychiatry")
    payload = mock_rest_client.generate_note.call_args.args[0]
    section_keys = [s["section_key"] for s in payload["note_sections_customization"]]
    assert "MENTAL_HEALTH_EXAM" in section_keys


def test_generic_payload_has_no_mental_health_exam() -> None:
    """The generic Nabla payload does NOT include the MENTAL_HEALTH_EXAM section customization."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
    backend.generate_note(Transcript(), visit_template_name="")
    payload = mock_rest_client.generate_note.call_args.args[0]
    section_keys = [s["section_key"] for s in payload["note_sections_customization"]]
    assert "MENTAL_HEALTH_EXAM" not in section_keys


def test_psychiatry_hpi_omits_medical_ros_scaffold() -> None:
    """The psychiatry HPI custom_instruction omits the generic medical ROS scaffold."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
    backend.generate_note(Transcript(), visit_template_name="Psychiatry")
    payload = mock_rest_client.generate_note.call_args.args[0]
    hpi_section = next(
        s for s in payload["note_sections_customization"] if s["section_key"] == "HISTORY_OF_PRESENT_ILLNESS"
    )
    instruction = hpi_section["custom_instruction"]
    assert "General:" not in instruction
    assert "HEENT:" not in instruction
    assert "Musculoskeletal:" not in instruction


def test_generic_hpi_includes_dynamic_ros() -> None:
    """The generic HPI custom_instruction asks for a dynamic ROS (Nabla picks
    systems) in the format the downstream parsers expect: an "ROS" marker line
    followed by "System: findings" rows with 1-3 word labels."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
    backend.generate_note(Transcript(), visit_template_name="")
    payload = mock_rest_client.generate_note.call_args.args[0]
    hpi_section = next(
        s for s in payload["note_sections_customization"] if s["section_key"] == "HISTORY_OF_PRESENT_ILLNESS"
    )
    instruction = hpi_section["custom_instruction"]
    assert "Review of Systems" in instruction
    assert "System: findings" in instruction
    assert "1-3 word name" in instruction


# --- AP merge gating (function-based per CLAUDE.md) ---


def test_merge_ap_when_psychiatry() -> None:
    """ASSESSMENT + PLAN sections merge into assessment_and_plan when merge_ap=True."""
    raw = {
        "title": "Psych Note",
        "sections": [
            {"key": "ASSESSMENT", "title": "Assessment", "text": "- Depression\n- Anxiety"},
            {"key": "PLAN", "title": "Plan", "text": "- Depression: Start SSRI\n- Anxiety: Continue therapy"},
        ],
    }
    result = NablaBackend._parse_note(raw, merge_ap=True)
    keys = [s.key for s in result.sections]
    assert "assessment_and_plan" in keys
    assert "ASSESSMENT" not in keys
    assert "PLAN" not in keys


def test_no_merge_ap_when_generic() -> None:
    """ASSESSMENT + PLAN sections remain separate when merge_ap=False."""
    raw = {
        "title": "Note",
        "sections": [
            {"key": "ASSESSMENT", "title": "Assessment", "text": "- Depression"},
            {"key": "PLAN", "title": "Plan", "text": "- Start SSRI"},
        ],
    }
    result = NablaBackend._parse_note(raw, merge_ap=False)
    keys = [s.key for s in result.sections]
    assert "assessment_and_plan" not in keys
    assert "ASSESSMENT" in keys
    assert "PLAN" in keys


def test_no_merge_when_assessment_and_plan_already_exists() -> None:
    """When assessment_and_plan exists in the raw payload, ASSESSMENT/PLAN are preserved without merge."""
    raw = {
        "title": "Note",
        "sections": [
            {"key": "assessment_and_plan", "title": "A&P", "text": "Already merged"},
            {"key": "ASSESSMENT", "title": "Assessment", "text": "- Depression"},
            {"key": "PLAN", "title": "Plan", "text": "- Start SSRI"},
        ],
    }
    result = NablaBackend._parse_note(raw, merge_ap=True)
    ap_sections = [s for s in result.sections if s.key == "assessment_and_plan"]
    assert len(ap_sections) == 1
    assert ap_sections[0].text == "Already merged"


def test_merge_ap_assessment_only() -> None:
    """When Nabla omits PLAN, assessment alone should still produce an A&P section."""
    raw = {
        "title": "Psych Note",
        "sections": [
            {"key": "ASSESSMENT", "title": "Assessment", "text": "- Depression\n- Anxiety"},
        ],
    }
    result = NablaBackend._parse_note(raw, merge_ap=True)
    keys = [s.key for s in result.sections]
    assert "assessment_and_plan" in keys
    assert "ASSESSMENT" not in keys


def test_merge_ap_plan_only() -> None:
    """When Nabla omits ASSESSMENT, plan alone should still produce an A&P section."""
    raw = {
        "title": "Psych Note",
        "sections": [
            {"key": "PLAN", "title": "Plan", "text": "- Depression: Start SSRI"},
        ],
    }
    result = NablaBackend._parse_note(raw, merge_ap=True)
    keys = [s.key for s in result.sections]
    assert "assessment_and_plan" in keys
    assert "PLAN" not in keys


# --- _reformat_plan_as_ap (function-based per CLAUDE.md) ---


def test_reformat_assessment_items_become_headers() -> None:
    """Assessment items are the block headers (diagnoses); plan actions are bullet bodies."""
    assessment = "- Generalized anxiety disorder\n- Panic attacks twice weekly"
    plan = "- Increase escitalopram for anxiety\n- Slow breathing during panic attacks"
    result = NablaBackend._reformat_plan_as_ap(assessment, plan)
    blocks = result.split("\n\n")
    assert len(blocks) == 2
    # Each block leads with the assessment diagnosis (non-bullet header).
    assert blocks[0].splitlines()[0] == "Generalized anxiety disorder"
    assert blocks[1].splitlines()[0] == "Panic attacks twice weekly"
    # Plan actions attach as bullets under the diagnosis they overlap most.
    assert "- Increase escitalopram for anxiety" in blocks[0]
    assert "- Slow breathing during panic attacks" in blocks[1]


def test_reformat_only_assessment_items_become_headers() -> None:
    """A plan action NEVER becomes a header — there is no catch-all 'General Plan'
    header. Unmatched actions attach to a real diagnosis (the last block), as bodies."""
    assessment = "- Generalized anxiety disorder"
    plan = "- Increase escitalopram dosage to 15 mg daily\n- Schedule follow-up in four weeks"
    result = NablaBackend._reformat_plan_as_ap(assessment, plan)
    blocks = result.split("\n\n")
    headers = [b.splitlines()[0] for b in blocks]
    # The only header is the diagnosis — no "General Plan", no plan-action headers.
    assert headers == ["Generalized anxiety disorder"]
    assert "General Plan" not in result
    # Both plan actions ride along as bodies under the diagnosis.
    assert "- Increase escitalopram dosage to 15 mg daily" in blocks[0]
    assert "- Schedule follow-up in four weeks" in blocks[0]


def test_reformat_zero_overlap_action_attaches_to_first_diagnosis() -> None:
    """A cross-cutting plan action with no overlap attaches to the FIRST (primary)
    diagnosis block, not an incidental last-listed one, and never its own header."""
    assessment = "- Generalized anxiety disorder\n- Hypothyroidism, well controlled"
    plan = "- Establish a safety plan for escalation of suicidal thoughts"
    result = NablaBackend._reformat_plan_as_ap(assessment, plan)
    blocks = result.split("\n\n")
    headers = [b.splitlines()[0] for b in blocks]
    assert headers == ["Generalized anxiety disorder", "Hypothyroidism, well controlled"]
    # Falls to the FIRST/primary block (zero-overlap default) — not under the
    # incidental "Hypothyroidism" comorbidity — and never a standalone header.
    assert "- Establish a safety plan for escalation of suicidal thoughts" in blocks[0]
    assert "Establish a safety plan" not in blocks[1]


def test_reformat_plan_empty_plan_returns_assessment_unchanged() -> None:
    """Empty plan: each assessment line already becomes a header downstream, so return unchanged."""
    from hyperscribe.scribe.commands.ap_split import parse_ap_blocks

    assessment = "- MDD\n- GAD"
    result = NablaBackend._reformat_plan_as_ap(assessment, "")
    assert result == assessment
    # Bullets with no preceding header → one headerless block; match_condition
    # refuses the empty header, so no phantom diagnose commands are minted.
    blocks = parse_ap_blocks(result)
    assert all(not b.header for b in blocks)


def test_reformat_both_empty_returns_empty() -> None:
    """No assessment and no plan → empty string."""
    assert NablaBackend._reformat_plan_as_ap("", "") == ""


def test_reformat_empty_assessment_emits_headerless_plan() -> None:
    """No assessment diagnoses: the plan surfaces as header-less bullets so no
    phantom *named* diagnosis is minted (parse_ap_blocks yields one header-less
    block that match_condition ignores)."""
    from hyperscribe.scribe.commands.ap_split import parse_ap_blocks

    plan = "- Increase escitalopram dosage\n- Schedule follow-up"
    result = NablaBackend._reformat_plan_as_ap("", plan)
    assert "- Increase escitalopram dosage" in result
    assert "- Schedule follow-up" in result
    blocks = parse_ap_blocks(result)
    assert all(not b.header for b in blocks)  # no named diagnosis header


def test_reformat_real_psychiatry_note_regression() -> None:
    """Regression for the live psychiatry misparse: plan ACTIONS must not become
    diagnosis headers, and the real 'passive suicidal ideation' diagnosis must
    survive as a header (it was previously absorbed under the 'establish a safety
    plan' plan action and lost)."""
    from hyperscribe.scribe.commands.ap_split import parse_ap_blocks

    assessment = (
        "- Ongoing anxiety with prominent worry, restlessness, and difficulty controlling anxious thoughts\n"
        "- Panic attacks occurring approximately twice weekly, characterized by palpitations and acute fear\n"
        "- Low mood present intermittently, secondary to anxiety\n"
        "- Sleep disturbance attributed to anxiety and racing thoughts\n"
        "- Passive suicidal ideation without plan or intent\n"
        "- Partial response to escitalopram 10 mg daily after five weeks, with initial side effects resolved"
    )
    plan = (
        "- Increase escitalopram dosage to 15 mg daily, to be taken in the morning with breakfast. "
        "Maintain this higher dose for one month before reassessment.\n"
        "- Referred to a cognitive behavioral therapist for initiation of CBT to address anxiety and panic symptoms.\n"
        "- Advise to reduce caffeine intake, limiting to one or two coffees earlier in the day.\n"
        "- Instruct to utilize slow breathing techniques during episodes of panic.\n"
        "- Establish a safety plan for management of suicidal ideation: if passive thoughts escalate to active "
        "intent or planning, immediately contact the psychiatrist, partner, the 988 crisis line, or present to ER.\n"
        "- Schedule a follow-up appointment in four weeks to monitor response to medication adjustment."
    )
    result = NablaBackend._reformat_plan_as_ap(assessment, plan)
    headers = [b.header for b in parse_ap_blocks(result)]

    # The real diagnosis survives as a header.
    assert "Passive suicidal ideation without plan or intent" in headers
    # Plan actions are NOT diagnosis headers, and there is NO catch-all header.
    assert not any(h.startswith("Increase escitalopram dosage") for h in headers)
    assert not any(h.startswith("Establish a safety plan") for h in headers)
    assert "General Plan" not in result
    # The safety-plan action attaches under the passive-SI diagnosis (word overlap).
    assert "Establish a safety plan for management of suicidal ideation" in result
    # Headers are EXACTLY the six assessment diagnoses — nothing more.
    assert headers == [
        "Ongoing anxiety with prominent worry, restlessness, and difficulty controlling anxious thoughts",
        "Panic attacks occurring approximately twice weekly, characterized by palpitations and acute fear",
        "Low mood present intermittently, secondary to anxiety",
        "Sleep disturbance attributed to anxiety and racing thoughts",
        "Passive suicidal ideation without plan or intent",
        "Partial response to escitalopram 10 mg daily after five weeks, with initial side effects resolved",
    ]


# --- _significant_words (function-based per CLAUDE.md) ---


def test_significant_words_filters_stop_words() -> None:
    """Common English stop words are filtered from the significant-words list."""
    words = NablaBackend._significant_words("the patient is in pain")
    assert "the" not in words
    assert "patient" in words
    assert "pain" in words


def test_significant_words_filters_short_words() -> None:
    """Words with length <= 2 are filtered out (drop articles/prepositions)."""
    words = NablaBackend._significant_words("a to be or go")
    # All <=2 chars or stop words
    assert words == []


def test_significant_words_strips_punctuation() -> None:
    """Punctuation is stripped before tokenization, including ICD-style code suffixes."""
    words = NablaBackend._significant_words("Depression (F32.9), active")
    assert "depression" in words
    assert "f32" in words
    assert "active" in words


def test_significant_words_splits_hyphenated_words() -> None:
    """Hyphenated medical phrases split into separate tokens; medical stop words are then filtered."""
    words = NablaBackend._significant_words("Attention-Deficit/Hyperactivity Disorder")
    assert "attention" in words
    assert "deficit" in words
    assert "hyperactivity" in words
    # "disorder" is filtered as a medical stop word (aligned with ap_split)
    assert "disorder" not in words


def test_significant_words_filters_medical_stop_words() -> None:
    """Generic medical wildcards (disorder/chronic/type) are filtered to avoid false overlap matches."""
    words = NablaBackend._significant_words("Major depressive disorder, chronic type")
    assert "major" in words
    assert "depressive" in words
    assert "disorder" not in words
    assert "chronic" not in words
    assert "type" not in words


# ---------------------------------------------------------------------------
# Psychiatry gating regression suite
# ---------------------------------------------------------------------------
# These tests pin the visit-template -> Nabla-payload gating so that the psych
# customization (Mental Health Exam section, no medical ROS scaffold in HPI,
# A&P merge with ICD-10 matching) ONLY fires when the user picks the
# "Psychiatry" visit template. They guard against silent regressions where
# changes downstream of `_PSYCHIATRY_TEMPLATE_NAMES` would leak psych behavior
# into default / subsequent-visit notes.


def _hpi_instruction(payload: dict[str, Any]) -> str:
    """Return the custom_instruction string from the HPI section customization."""
    hpi = next(s for s in payload["note_sections_customization"] if s["section_key"] == "HISTORY_OF_PRESENT_ILLNESS")
    return str(hpi["custom_instruction"])


def _section_keys(payload: dict[str, Any]) -> list[str]:
    """Return the list of section_key values in the Nabla payload's customization."""
    return [s["section_key"] for s in payload["note_sections_customization"]]


def test_default_template_does_not_trigger_psych_path() -> None:
    """An empty visit_template_name uses the generic template and no psych customization."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript(), visit_template_name="")

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
    assert "MENTAL_HEALTH_EXAM" not in _section_keys(payload)
    # Generic HPI carries a Review of Systems (dynamic — Nabla picks systems).
    assert "Review of Systems" in _hpi_instruction(payload)


def test_subsequent_visit_does_not_trigger_psych_path() -> None:
    """A non-psych template name (e.g. 'Subsequent Visit') uses the generic template."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript(), visit_template_name="Subsequent Visit")

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
    assert "MENTAL_HEALTH_EXAM" not in _section_keys(payload)
    assert "Review of Systems" in _hpi_instruction(payload)


def test_psychiatry_template_triggers_psych_path() -> None:
    """The 'Psychiatry' template routes to the psych Nabla template and adds the Mental Health Exam section."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript(), visit_template_name="Psychiatry")

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "PSYCHIATRY_MULTIPLE_SECTIONS_AP_MERGED"
    keys = _section_keys(payload)
    assert "MENTAL_HEALTH_EXAM" in keys
    # Psych branch should NOT carry the generic medical ROS scaffold in HPI.
    assert "HEENT:" not in _hpi_instruction(payload)


def test_unknown_template_does_not_trigger_psych_path() -> None:
    """An unrecognized template name falls back to the generic template, no psych customization."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript(), visit_template_name="Bogus Template")

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
    assert "MENTAL_HEALTH_EXAM" not in _section_keys(payload)


def test_psychiatry_match_is_exact_case_sensitive() -> None:
    """Lowercase 'psychiatry' does NOT match — gating is intentionally exact-match."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript(), visit_template_name="psychiatry")

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
    assert "MENTAL_HEALTH_EXAM" not in _section_keys(payload)


def test_psychiatry_match_ignores_trailing_whitespace_by_design() -> None:
    """'Psychiatry ' (trailing space) does NOT match — gating is intentionally exact-match."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    backend.generate_note(Transcript(), visit_template_name="Psychiatry ")

    payload = mock_rest_client.generate_note.call_args.args[0]
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
    assert "MENTAL_HEALTH_EXAM" not in _section_keys(payload)


def test_none_template_does_not_crash() -> None:
    """`visit_template_name=None` falls back to default behavior without raising.

    session_view coerces None to '' before calling generate_note, but pin the
    backend contract here in case any future caller forwards a raw None.
    """
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    # Cast to satisfy the str-typed parameter while exercising the None path
    # that callers may produce (e.g. selectedTemplate?.name -> null in JS).
    backend.generate_note(Transcript(), visit_template_name=None)  # type: ignore[arg-type]

    payload = mock_rest_client.generate_note.call_args.args[0]
    # `None in frozenset({"Psychiatry"})` is False → generic path.
    assert payload["note_template_key"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"
    assert "MENTAL_HEALTH_EXAM" not in _section_keys(payload)


def test_ap_merge_only_when_psychiatry() -> None:
    """ASSESSMENT + PLAN sections from Nabla are merged into assessment_and_plan ONLY under psychiatry.

    Without merge_ap (default), the two sections remain separate. With merge_ap (psychiatry),
    they collapse into a single assessment_and_plan section ready for ICD-10 matching.
    """
    raw = {
        "title": "Note",
        "sections": [
            {"key": "assessment", "title": "Assessment", "text": "- Depression with low mood"},
            {"key": "plan", "title": "Plan", "text": "- Depression: Start sertraline"},
        ],
    }

    parsed_default = NablaBackend._parse_note(raw, merge_ap=False)
    default_keys = {s.key.lower() for s in parsed_default.sections}
    assert "assessment" in default_keys
    assert "plan" in default_keys
    assert "assessment_and_plan" not in default_keys

    parsed_psych = NablaBackend._parse_note(raw, merge_ap=True)
    psych_keys = {s.key.lower() for s in parsed_psych.sections}
    assert "assessment" not in psych_keys
    assert "plan" not in psych_keys
    assert "assessment_and_plan" in psych_keys


def test_generate_note_default_does_not_merge_ap() -> None:
    """When generate_note runs without psychiatry, the parser leaves assessment/plan untouched."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {
        "title": "Note",
        "sections": [
            {"key": "assessment", "title": "Assessment", "text": "- Notes"},
            {"key": "plan", "title": "Plan", "text": "- Naproxen"},
        ],
    }

    result = backend.generate_note(Transcript(), visit_template_name="")
    keys = {s.key.lower() for s in result.sections}
    assert "assessment_and_plan" not in keys
    assert "assessment" in keys
    assert "plan" in keys


def test_generate_note_psychiatry_merges_ap() -> None:
    """When generate_note runs with psychiatry, the parser merges assessment+plan."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {
        "title": "Note",
        "sections": [
            {"key": "assessment", "title": "Assessment", "text": "- Depression"},
            {"key": "plan", "title": "Plan", "text": "- Depression: Start SSRI"},
        ],
    }

    result = backend.generate_note(Transcript(), visit_template_name="Psychiatry")
    keys = {s.key.lower() for s in result.sections}
    assert "assessment_and_plan" in keys
    assert "assessment" not in keys
    assert "plan" not in keys


def test_psychiatry_hpi_prompt_only_when_psychiatry() -> None:
    """Both HPIs append a dynamic ROS, but with different formats: generic uses a
    medical ROS ("System: findings"); psychiatry uses a psychiatric ROS ("Category: findings")."""
    backend, mock_rest_client = _make_backend()
    mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}

    # Default visit: appends the medical ROS request.
    backend.generate_note(Transcript(), visit_template_name="")
    generic_hpi = _hpi_instruction(mock_rest_client.generate_note.call_args.args[0])
    assert "Review of Systems" in generic_hpi
    assert "System: findings" in generic_hpi
    assert "Category: findings" not in generic_hpi

    # Psychiatry visit: appends a psychiatric ROS using the "Category: findings" format.
    backend.generate_note(Transcript(), visit_template_name="Psychiatry")
    psych_hpi = _hpi_instruction(mock_rest_client.generate_note.call_args.args[0])
    assert "psychiatric Review of Systems" in psych_hpi
    assert "Category: findings" in psych_hpi
    assert "System: findings" not in psych_hpi
    # Both HPIs share the "structured summary" guidance and opening template.
    assert "structured summary" in psych_hpi.lower()
    assert "structured summary" in generic_hpi.lower()


# --- Public template helpers (is_psychiatry_template / near_miss) ---


def test_is_psychiatry_template_exact_match() -> None:
    """Public helper exposes the same exact-match gate generate_note uses internally."""
    assert NablaBackend.is_psychiatry_template("Psychiatry") is True
    assert NablaBackend.is_psychiatry_template("") is False
    assert NablaBackend.is_psychiatry_template("Subsequent Visit") is False
    # Case/whitespace drift falls through to False (server-controlled name, no normalization).
    assert NablaBackend.is_psychiatry_template("psychiatry") is False
    assert NablaBackend.is_psychiatry_template("Psychiatry ") is False


def test_is_psychiatry_template_near_miss_detects_lookalikes() -> None:
    """Near-miss detector fires on operator templates that look like psychiatry but don't exact-match."""
    assert NablaBackend.is_psychiatry_template_near_miss("Psychiatry Follow-up") is True
    assert NablaBackend.is_psychiatry_template_near_miss("psychiatry") is True
    assert NablaBackend.is_psychiatry_template_near_miss("Psychiatry ") is True
    assert NablaBackend.is_psychiatry_template_near_miss("PSYCH consult") is True


def test_is_psychiatry_template_near_miss_silent_on_exact_match() -> None:
    """Exact-match templates do NOT trigger NEAR_MISS (only the gate itself fires)."""
    assert NablaBackend.is_psychiatry_template_near_miss("Psychiatry") is False


def test_is_psychiatry_template_near_miss_silent_on_non_psych() -> None:
    """Templates with no 'psych' substring do NOT trigger NEAR_MISS."""
    assert NablaBackend.is_psychiatry_template_near_miss("Subsequent Visit") is False
    assert NablaBackend.is_psychiatry_template_near_miss("") is False
    assert NablaBackend.is_psychiatry_template_near_miss("Primary Care") is False
