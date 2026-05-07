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


# --- Psychiatry template tests ---


class TestPsychiatryTemplateMatching:
    """Verify visit template name matching.

    The template name comes from the /visit-templates endpoint (server-controlled),
    so it's always exactly "Psychiatry" — no need for case-insensitive matching.
    """

    def test_psychiatry_selects_psychiatry_template(self) -> None:
        backend, mock_rest_client = _make_backend()
        mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
        backend.generate_note(Transcript(), visit_template_name="Psychiatry")
        payload = mock_rest_client.generate_note.call_args.args[0]
        assert payload["note_template"] == "PSYCHIATRY_MULTIPLE_SECTIONS"

    def test_non_psychiatry_uses_generic(self) -> None:
        backend, mock_rest_client = _make_backend()
        mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
        backend.generate_note(Transcript(), visit_template_name="Primary Care")
        payload = mock_rest_client.generate_note.call_args.args[0]
        assert payload["note_template"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"

    def test_empty_name_uses_generic(self) -> None:
        backend, mock_rest_client = _make_backend()
        mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
        backend.generate_note(Transcript(), visit_template_name="")
        payload = mock_rest_client.generate_note.call_args.args[0]
        assert payload["note_template"] == "GENERIC_MULTIPLE_SECTIONS_AP_MERGED"

    def test_psychiatry_payload_has_mental_health_exam(self) -> None:
        backend, mock_rest_client = _make_backend()
        mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
        backend.generate_note(Transcript(), visit_template_name="Psychiatry")
        payload = mock_rest_client.generate_note.call_args.args[0]
        section_keys = [s["section_key"] for s in payload["note_sections_customization"]]
        assert "MENTAL_HEALTH_EXAM" in section_keys

    def test_generic_payload_has_no_mental_health_exam(self) -> None:
        backend, mock_rest_client = _make_backend()
        mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
        backend.generate_note(Transcript(), visit_template_name="")
        payload = mock_rest_client.generate_note.call_args.args[0]
        section_keys = [s["section_key"] for s in payload["note_sections_customization"]]
        assert "MENTAL_HEALTH_EXAM" not in section_keys

    def test_psychiatry_hpi_omits_medical_ros_scaffold(self) -> None:
        backend, mock_rest_client = _make_backend()
        mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
        backend.generate_note(Transcript(), visit_template_name="Psychiatry")
        payload = mock_rest_client.generate_note.call_args.args[0]
        hpi_section = next(s for s in payload["note_sections_customization"]
                          if s["section_key"] == "HISTORY_OF_PRESENT_ILLNESS")
        instruction = hpi_section["custom_instruction"]
        assert "General:" not in instruction
        assert "HEENT:" not in instruction
        assert "Musculoskeletal:" not in instruction

    def test_generic_hpi_includes_medical_ros_scaffold(self) -> None:
        backend, mock_rest_client = _make_backend()
        mock_rest_client.generate_note.return_value = {"title": "Note", "sections": []}
        backend.generate_note(Transcript(), visit_template_name="")
        payload = mock_rest_client.generate_note.call_args.args[0]
        hpi_section = next(s for s in payload["note_sections_customization"]
                          if s["section_key"] == "HISTORY_OF_PRESENT_ILLNESS")
        instruction = hpi_section["custom_instruction"]
        assert "General:" in instruction
        assert "HEENT:" in instruction
        assert "Musculoskeletal:" in instruction


class TestAPMerge:
    """Verify AP merge only runs for psychiatry template."""

    def test_merge_ap_when_psychiatry(self) -> None:
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

    def test_no_merge_ap_when_generic(self) -> None:
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

    def test_no_merge_when_assessment_and_plan_already_exists(self) -> None:
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


class TestReformatPlanAsAP:
    """Test _reformat_plan_as_ap word overlap matching and output formatting."""

    def test_basic_merge(self) -> None:
        assessment = "- Depression with low mood"
        plan = "- Depression: Start sertraline 50mg"
        result = NablaBackend._reformat_plan_as_ap(assessment, plan)
        assert "Depression" in result
        assert "- Depression with low mood" in result
        assert "- Start sertraline 50mg" in result

    def test_multiple_blocks(self) -> None:
        assessment = "- Depression\n- Anxiety disorder"
        plan = "- Depression: Start SSRI\n- Anxiety: Continue therapy"
        result = NablaBackend._reformat_plan_as_ap(assessment, plan)
        # Depression assessment should be under Depression plan, not Anxiety
        blocks = result.split("\n\n")
        assert len(blocks) == 2
        assert "Depression" in blocks[0]
        assert "- Depression" in blocks[0]
        assert "Anxiety" in blocks[1]

    def test_unmatched_assessment_becomes_standalone(self) -> None:
        """Assessment items with no word overlap should NOT pile under block 0."""
        assessment = "- Completely unrelated finding xyz"
        plan = "- Depression: Start SSRI\n- Anxiety: Continue therapy"
        result = NablaBackend._reformat_plan_as_ap(assessment, plan)
        blocks = result.split("\n\n")
        # Should be 3 blocks: Depression, Anxiety, and the unmatched standalone
        assert len(blocks) == 3
        assert "Completely unrelated finding xyz" in blocks[2]
        # The unmatched item should NOT appear under the Depression block
        assert "unrelated" not in blocks[0]

    def test_multiple_unmatched_all_standalone(self) -> None:
        assessment = "- Alpha bravo\n- Charlie delta"
        plan = "- Depression: Start SSRI"
        result = NablaBackend._reformat_plan_as_ap(assessment, plan)
        blocks = result.split("\n\n")
        # 1 plan block + 2 standalone unmatched items
        assert len(blocks) == 3
        assert "Alpha bravo" in blocks[1]
        assert "Charlie delta" in blocks[2]

    def test_empty_plan_returns_assessment_headers(self) -> None:
        assessment = "- Depression\n- Anxiety"
        plan = ""
        result = NablaBackend._reformat_plan_as_ap(assessment, plan)
        assert result == "Depression\n\nAnxiety"

    def test_empty_assessment(self) -> None:
        assessment = ""
        plan = "- Depression: Start SSRI"
        result = NablaBackend._reformat_plan_as_ap(assessment, plan)
        assert "Depression" in result
        assert "Start SSRI" in result


class TestSignificantWords:
    """Test _significant_words filtering."""

    def test_filters_stop_words(self) -> None:
        words = NablaBackend._significant_words("the patient is in pain")
        assert "the" not in words
        assert "patient" in words
        assert "pain" in words

    def test_filters_short_words(self) -> None:
        words = NablaBackend._significant_words("a to be or go")
        # All <=2 chars or stop words
        assert words == []

    def test_strips_punctuation(self) -> None:
        words = NablaBackend._significant_words("Depression (F32.9), active")
        assert "depression" in words
        assert "f329" in words
        assert "active" in words
