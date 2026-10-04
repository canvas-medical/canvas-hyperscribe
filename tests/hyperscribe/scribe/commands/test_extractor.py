from hyperscribe.scribe.backend.models import ClinicalNote, CodingEntry, NoteSection, Observation
from hyperscribe.scribe.commands.extractor import (
    classify_vitals_source,
    extract_commands,
    extract_vitals_with_telemetry,
    parse_ros_subsections,
)
from hyperscribe.scribe.commands.vitals import REFUSAL_REASON_OUT_OF_RANGE


def _loinc_obs(code: str, value: str, *, unit: str = "", display: str = "") -> Observation:
    """Build an Observation whose only coding entry is a LOINC code."""
    return Observation(
        display=display or code,
        value=value,
        unit=unit,
        coding=[CodingEntry(system="LOINC", code=code, display=display)],
    )


def test_routes_chief_complaint_to_rfv() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="chief_complaint", title="CC", text="Lower back pain.")],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "rfv"
    assert proposals[0].section_key == "chief_complaint"


def test_routes_hpi() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="history_of_present_illness", title="HPI", text="Onset 2 weeks ago.")],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "hpi"
    assert proposals[0].section_key == "history_of_present_illness"


def test_routes_review_of_systems() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="review_of_systems",
                title="Review of Systems",
                text="General: No fever.\nSkin: No rash.\nHEENT: Normal.",
            )
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "ros"
    assert proposals[0].section_key == "_ros"
    secs = proposals[0].data["sections"]
    assert len(secs) == 3
    assert secs[0]["title"] == "General"
    assert secs[0]["text"] == "No fever."
    assert secs[1]["title"] == "Skin"
    assert secs[2]["title"] == "HEENT"
    assert proposals[0].display == "General | Skin | HEENT"


def test_ros_fallback_no_system_headers() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="review_of_systems", title="Review of Systems", text="All systems negative.")],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].data["sections"][0]["title"] == "Review of Systems"
    assert proposals[0].data["sections"][0]["text"] == "All systems negative."


def test_routes_plan() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="plan", title="Plan", text="Start naproxen.")],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "plan"
    assert proposals[0].section_key == "plan"


def test_routes_vitals() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="BP 120/80, HR 72")],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "vitals"
    assert proposals[0].section_key == "vitals"


def test_assessment_and_plan_routed_to_plan() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="assessment_and_plan", title="Assessment & Plan", text="Migraine. Start sumatriptan.")
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "plan"
    assert proposals[0].section_key == "assessment_and_plan"


def test_appointments_routed_to_plan() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="appointments", title="Appointments", text="Follow-up in 2 weeks.")],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "plan"
    assert proposals[0].section_key == "appointments"
    assert proposals[0].data == {"narrative": "Follow-up in 2 weeks."}


def test_physical_exam_with_subsections() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="physical_exam",
                title="Physical Exam",
                text="General: Well-appearing\nLungs: CTA bilaterally\nHeart: RRR, no murmurs",
            )
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "physical_exam"
    assert proposals[0].section_key == "physical_exam"
    secs = proposals[0].data["sections"]
    assert len(secs) == 3
    assert secs[0]["title"] == "General"
    assert secs[0]["text"] == "Well-appearing"
    assert secs[1]["title"] == "Lungs"
    assert secs[2]["title"] == "Heart"
    assert proposals[0].display == "General | Lungs | Heart"


def test_physical_exam_fallback_no_headers() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="physical_exam", title="Physical Exam", text="Normal gait.")],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "physical_exam"
    assert proposals[0].data["sections"][0]["title"] == "Physical Exam"
    assert proposals[0].data["sections"][0]["text"] == "Normal gait."


def test_physical_exam_empty_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="physical_exam", title="Physical Exam", text="   ")],
    )
    assert extract_commands(note) == []


def test_empty_sections() -> None:
    note = ClinicalNote(title="Note", sections=[])
    assert extract_commands(note) == []


def test_empty_text_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text=""),
            NoteSection(key="plan", title="Plan", text="   "),
        ],
    )
    assert extract_commands(note) == []


def test_unknown_section_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="some_custom_section", title="Custom", text="Some text here.")],
    )
    assert extract_commands(note) == []


def test_unparseable_vitals_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="Patient appears well.")],
    )
    assert extract_commands(note) == []


def test_display_is_full_text() -> None:
    long_text = "Patient presents with a very long narrative. " + "x" * 200
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="chief_complaint", title="CC", text=long_text)],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].display == long_text


def test_current_medications_only_chart_review() -> None:
    """Medications produce only a chart_review, not individual medication_statement commands."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="current_medications",
                title="Current Medications",
                text="- Lisinopril 10mg\n- Metformin 500mg\n- Atorvastatin 20mg",
            )
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "chart_review"


def test_current_medications_empty_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="current_medications", title="Meds", text="   ")],
    )
    assert extract_commands(note) == []


def test_full_multiple_sections_note() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Headaches for two weeks."),
            NoteSection(key="history_of_present_illness", title="HPI", text="Mostly right-sided."),
            NoteSection(key="vitals", title="Vitals", text="BP 130/85"),
            NoteSection(key="physical_exam", title="PE", text="General: Well-appearing"),
            NoteSection(key="assessment_and_plan", title="Assessment & Plan", text="Migraine. Start sumatriptan 50mg."),
            NoteSection(key="current_medications", title="Meds", text="- Aspirin 81mg"),
        ],
    )
    proposals = extract_commands(note)
    types = [p.command_type for p in proposals]
    assert types == ["rfv", "hpi", "vitals", "plan", "physical_exam", "chart_review"]


def test_routes_history_sections_to_history_review() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="past_medical_history", title="PMH", text="Hypertension"),
            NoteSection(key="past_surgical_history", title="PSH", text="Appendectomy 2010"),
            NoteSection(key="past_obstetric_history", title="POH", text="G2P2"),
            NoteSection(key="family_history", title="FH", text="Father had diabetes"),
            NoteSection(key="social_history", title="SH", text="Non-smoker"),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "history_review"
    assert proposals[0].section_key == "_history_review"
    assert len(proposals[0].data["sections"]) == 5
    assert proposals[0].display == "PMH | PSH | POH | FH | SH"


def test_history_review_partial_sections() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="past_medical_history", title="PMH", text="Hypertension"),
            NoteSection(key="social_history", title="SH", text="Non-smoker"),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "history_review"
    assert len(proposals[0].data["sections"]) == 2


def test_history_review_empty_text_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="past_medical_history", title="PMH", text=""),
            NoteSection(key="family_history", title="FH", text="   "),
        ],
    )
    assert extract_commands(note) == []


def test_history_review_combined_with_other_commands() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Chest pain"),
            NoteSection(key="history_of_present_illness", title="HPI", text="Onset yesterday."),
            NoteSection(key="past_medical_history", title="PMH", text="Hypertension"),
            NoteSection(key="family_history", title="FH", text="Heart disease"),
            NoteSection(key="plan", title="Plan", text="Order ECG."),
        ],
    )
    proposals = extract_commands(note)
    types = [p.command_type for p in proposals]
    assert types == ["rfv", "hpi", "plan", "history_review"]


def test_routes_chart_sections_to_chart_review() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="current_medications", title="Meds", text="- Lisinopril 10mg"),
            NoteSection(key="allergies", title="Allergies", text="Penicillin (rash)"),
            NoteSection(key="immunizations", title="Immunizations", text="Flu 2025"),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "chart_review"
    assert proposals[0].section_key == "_chart_review"
    assert len(proposals[0].data["sections"]) == 3
    assert proposals[0].display == "Meds Discussed | Allergies Discussed | Immunizations"


def test_chart_review_partial_sections() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="allergies", title="Allergies", text="NKDA"),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "chart_review"
    assert len(proposals[0].data["sections"]) == 1


def test_chart_review_empty_text_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="allergies", title="Allergies", text=""),
            NoteSection(key="immunizations", title="Immunizations", text="   "),
        ],
    )
    assert extract_commands(note) == []


def test_allergies_only_chart_review() -> None:
    """Allergies produce only a chart_review, not individual allergy commands."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="allergies", title="Allergies", text="- Penicillin (rash)\n- Sulfa drugs (hives)"),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "chart_review"


# --- parse_ros_subsections ---


def test_routes_vitals_with_observations() -> None:
    """When observations are supplied, the vitals proposal picks up fields the regex misses."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="vitals",
                title="Vitals",
                # Verbose Nabla format — the unpatched regex would drop SpO2 here.
                text="* Heart rate: 74 bpm\n* O2 saturation: 94%",
            )
        ],
    )
    observations = [
        _loinc_obs("85354-9", "103/56", unit="mmHg", display="Blood pressure"),
        _loinc_obs("9279-1", "16", unit="/min", display="Respiratory rate"),
    ]
    proposals = extract_commands(note, observations=observations)
    assert len(proposals) == 1
    assert proposals[0].command_type == "vitals"
    data = proposals[0].data
    assert data["pulse"] == 74  # from regex (Heart rate line)
    assert data["oxygen_saturation"] == 94  # from regex (O2 saturation line)
    assert data["blood_pressure_systole"] == 103  # from observation
    assert data["blood_pressure_diastole"] == 56  # from observation
    assert data["respiration_rate"] == 16  # from observation


def test_routes_vitals_observations_only_no_section() -> None:
    """Vitals proposal is emitted even when there is no vitals section, as long as observations carry data."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Routine checkup."),
        ],
    )
    observations = [_loinc_obs("8867-4", "74", unit="bpm", display="Heart rate")]
    proposals = extract_commands(note, observations=observations)
    types = [p.command_type for p in proposals]
    assert "vitals" in types
    vitals = next(p for p in proposals if p.command_type == "vitals")
    assert vitals.data["pulse"] == 74
    assert vitals.section_key == "vitals"


def test_routes_vitals_no_section_no_observations_omits_vitals() -> None:
    """No vitals section and no observations means no vitals proposal."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Routine checkup."),
        ],
    )
    proposals = extract_commands(note, observations=[])
    types = [p.command_type for p in proposals]
    assert "vitals" not in types


def test_routes_vitals_position_preserved_among_other_commands() -> None:
    """Vitals proposal lands in section-order, even when emitted via observations."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Headache"),
            NoteSection(key="vitals", title="Vitals", text=""),
            NoteSection(key="plan", title="Plan", text="Naproxen 500mg"),
        ],
    )
    observations = [_loinc_obs("8867-4", "74", unit="bpm", display="Heart rate")]
    proposals = extract_commands(note, observations=observations)
    types = [p.command_type for p in proposals]
    assert types == ["rfv", "vitals", "plan"]


def test_extract_commands_observations_default_empty() -> None:
    """Backwards-compat: callers that don't supply observations get the original regex-only behaviour."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="BP 120/80, HR 72")],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert proposals[0].command_type == "vitals"
    assert proposals[0].data["pulse"] == 72


def test_parse_ros_subsections_standard() -> None:
    text = "CONSTITUTIONAL: Denies fever, chills.\nEYES: Denies visual changes."
    result = parse_ros_subsections(text)
    assert len(result) == 2
    assert result[0] == {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever, chills."}
    assert result[1] == {"key": "eyes", "title": "EYES", "text": "Denies visual changes."}


def test_parse_ros_subsections_empty() -> None:
    assert parse_ros_subsections("") == []


def test_parse_ros_subsections_multiword_title() -> None:
    text = "MOUTH/THROAT/VOICE: Denies sore throat."
    result = parse_ros_subsections(text)
    assert len(result) == 1
    assert result[0]["title"] == "MOUTH/THROAT/VOICE"


# --- classify_vitals_source --------------------------------------------------------
# These tests pin the telemetry signal used by ``post_generate_summary`` to emit a
# VITALS_SOURCE audit event. The signal lets us measure observation-vs-regex
# reliability in prod and eventually retire the loser parser.


def test_classify_vitals_source_observations_only() -> None:
    """Only observations populated → ``observations``."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="")],
    )
    observations = [_loinc_obs("8867-4", "74", unit="bpm", display="Heart rate")]
    assert classify_vitals_source(note, observations) == "observations"


def test_classify_vitals_source_regex_only() -> None:
    """Only the vitals section text populated → ``regex``."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="BP 120/80")],
    )
    assert classify_vitals_source(note, []) == "regex"


def test_classify_vitals_source_both() -> None:
    """Both observations and regex populated → ``both``."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="BP 120/80")],
    )
    observations = [_loinc_obs("8867-4", "74", unit="bpm", display="Heart rate")]
    assert classify_vitals_source(note, observations) == "both"


def test_classify_vitals_source_none() -> None:
    """Nothing populated (no section, no observations) → ``none``."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="chief_complaint", title="CC", text="Headache")],
    )
    assert classify_vitals_source(note, []) == "none"


def test_classify_vitals_source_section_present_but_unparseable() -> None:
    """Vitals section text that the regex cannot parse → ``none`` (not ``regex``)."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="Patient appears well.")],
    )
    assert classify_vitals_source(note, []) == "none"


def test_classify_vitals_source_bp_panel_fully_refused_is_none() -> None:
    """Fix 2: a fully-refused BP-panel observation must classify as ``none``, not ``observations``.

    Before the fix, ``classify_vitals_source`` re-parsed raw observations standalone (skipping
    validation) and declared the source ``observations`` even when no observation field
    survived validation. The fix routes through the same extraction that builds the
    proposal, so the source label reflects what actually landed in the final data dict.
    """
    note = ClinicalNote(title="Note", sections=[NoteSection(key="vitals", title="Vitals", text="")])
    observations = [_loinc_obs("85354-9", "999/999", unit="mmHg", display="Blood pressure")]
    assert classify_vitals_source(note, observations) == "none"


# --- extract_vitals_with_telemetry -------------------------------------------------
# Module-level wrapper around ``VitalsParser.extract_with_telemetry`` that adds the
# section-key tagging and the "no vitals section + no observations → empty result"
# short-circuit. Used by ``post_generate_summary`` to emit one VITALS_SOURCE + one
# (optional) VITALS_FIELD_REFUSED from a single extraction.


def test_extract_vitals_with_telemetry_happy_path() -> None:
    """Happy path: a vitals section with valid data produces a proposal, no refusals, regex source."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="BP 120/80, HR 72")],
    )
    result = extract_vitals_with_telemetry(note, [])
    assert result.proposal is not None
    assert result.proposal.section_key == "vitals"
    assert result.refusals == []
    assert result.source == "regex"


def test_extract_vitals_with_telemetry_no_section_no_obs_is_empty() -> None:
    """No vitals section + no observations short-circuits to (None, [], "none")."""
    note = ClinicalNote(title="Note", sections=[])
    result = extract_vitals_with_telemetry(note, [])
    assert result.proposal is None
    assert result.refusals == []
    assert result.source == "none"


def test_extract_vitals_with_telemetry_out_of_range_pulse_refused() -> None:
    """Refusals propagate through the module-level wrapper."""
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="vitals", title="Vitals", text="HR 25, BP 120/80")],
    )
    result = extract_vitals_with_telemetry(note, [])
    assert result.proposal is not None
    assert [(r.field, r.reason) for r in result.refusals] == [
        ("pulse", REFUSAL_REASON_OUT_OF_RANGE),
    ]
    # Pulse was refused but BP survived → still regex source.
    assert result.source == "regex"
    assert "pulse" not in result.proposal.data


# --- mental_status_exam (psychiatry-only, separate from ROS) ---


def test_mental_status_exam_and_ros_coexist() -> None:
    """Under the psychiatry gate, review_of_systems and mental_health_exam produce
    two distinct commands: a baseline ROS and a separate Mental Status Exam."""
    note = ClinicalNote(
        title="Psych Note",
        sections=[
            NoteSection(
                key="review_of_systems",
                title="Review of Systems",
                text="General: No fever.\nSkin: No rash.",
            ),
            NoteSection(
                key="MENTAL_HEALTH_EXAM",
                title="Mental Status Exam",
                text="Depressive Symptoms: Denied\nAnxiety Symptoms: Irritability noted",
            ),
        ],
    )
    proposals = extract_commands(note, is_psychiatry=True)

    ros_proposals = [p for p in proposals if p.command_type == "ros"]
    assert len(ros_proposals) == 1
    ros_titles = [s["title"] for s in ros_proposals[0].data["sections"]]
    assert "General" in ros_titles
    assert "Depressive Symptoms" not in ros_titles  # MSE content does NOT leak into ROS

    mse_proposals = [p for p in proposals if p.command_type == "mental_status_exam"]
    assert len(mse_proposals) == 1
    assert mse_proposals[0].section_key == "mental_status_exam"
    mse_titles = [s["title"] for s in mse_proposals[0].data["sections"]]
    assert "Depressive Symptoms" in mse_titles
    assert "Anxiety Symptoms" in mse_titles


def test_mental_status_exam_only() -> None:
    """Under the psychiatry gate, mental_health_exam alone produces a mental_status_exam command (not ros)."""
    note = ClinicalNote(
        title="Psych Note",
        sections=[
            NoteSection(
                key="MENTAL_HEALTH_EXAM",
                title="Mental Status Exam",
                text="Hallucinations: Auditory denied\nDelusions/Paranoia: Recurring paranoid thoughts",
            ),
        ],
    )
    proposals = extract_commands(note, is_psychiatry=True)
    assert not [p for p in proposals if p.command_type == "ros"]
    mse_proposals = [p for p in proposals if p.command_type == "mental_status_exam"]
    assert len(mse_proposals) == 1
    secs = mse_proposals[0].data["sections"]
    assert any(s["title"] == "Hallucinations" for s in secs)
    assert any(s["title"] == "Delusions/Paranoia" for s in secs)


def test_mental_status_exam_ordered_before_physical_exam() -> None:
    """The MSE proposal is emitted before the Physical Exam proposal (UI renders MSE above PE)."""
    note = ClinicalNote(
        title="Psych Note",
        sections=[
            NoteSection(key="physical_exam", title="Physical Exam", text="General: Well-appearing."),
            NoteSection(key="MENTAL_HEALTH_EXAM", title="Mental Status Exam", text="Mood: Euthymic."),
        ],
    )
    proposals = extract_commands(note, is_psychiatry=True)
    types = [p.command_type for p in proposals]
    assert "mental_status_exam" in types
    assert "physical_exam" in types
    assert types.index("mental_status_exam") < types.index("physical_exam")


def test_mental_health_exam_ignored_when_not_psychiatry() -> None:
    """Without the psychiatry gate, mental_health_exam is ignored entirely (no MSE command)."""
    note = ClinicalNote(
        title="Visit",
        sections=[
            NoteSection(
                key="MENTAL_HEALTH_EXAM",
                title="Mental Status Exam",
                text="Mood: Euthymic\nInsight: Good",
            ),
        ],
    )
    proposals = extract_commands(note, is_psychiatry=False)
    assert not [p for p in proposals if p.command_type == "mental_status_exam"]
    assert not [p for p in proposals if p.command_type == "ros"]


def test_review_of_systems_used_when_no_mental_health_exam() -> None:
    """Without mental_health_exam, falls back to review_of_systems."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="review_of_systems",
                title="Review of Systems",
                text="General: No fever.\nSkin: No rash.",
            ),
        ],
    )
    proposals = extract_commands(note)
    ros_proposals = [p for p in proposals if p.command_type == "ros"]
    assert len(ros_proposals) == 1
    assert ros_proposals[0].data["sections"][0]["title"] == "General"


def test_mental_status_exam_fallback_uses_correct_label() -> None:
    """Psych gate + unparseable mental_health_exam falls back to 'Mental Status Exam' as the label."""
    note = ClinicalNote(
        title="Psych Note",
        sections=[
            NoteSection(
                key="MENTAL_HEALTH_EXAM",
                title="Mental Status Exam",
                text="Patient appears stable today with improved insight and no active SI/HI.",
            ),
        ],
    )
    proposals = extract_commands(note, is_psychiatry=True)
    mse_proposals = [p for p in proposals if p.command_type == "mental_status_exam"]
    assert len(mse_proposals) == 1
    assert mse_proposals[0].data["sections"][0]["title"] == "Mental Status Exam"
    assert mse_proposals[0].data["sections"][0]["key"] == "mental_status_exam"


def test_review_of_systems_fallback_uses_correct_label() -> None:
    """When review_of_systems has no parseable headers, fallback label should be 'Review of Systems'."""
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="review_of_systems",
                title="Review of Systems",
                text="No acute complaints reported by patient.",
            ),
        ],
    )
    proposals = extract_commands(note)
    ros_proposals = [p for p in proposals if p.command_type == "ros"]
    assert len(ros_proposals) == 1
    assert ros_proposals[0].data["sections"][0]["title"] == "Review of Systems"
    assert ros_proposals[0].data["sections"][0]["key"] == "review_of_systems"


def test_parse_ros_subsections_preserves_pre_header_narrative() -> None:
    """Narrative text before the first category header should be preserved."""
    text = (
        "Patient appears stable today with improved insight.\n"
        "Depressive Symptoms: Persistent low mood, anhedonia.\n"
        "Anxiety Symptoms: Mild worry about job."
    )
    result = parse_ros_subsections(text)
    assert len(result) == 2
    # Pre-header narrative should be prepended to the first subsection
    assert "Patient appears stable" in result[0]["text"]
    assert "Persistent low mood" in result[0]["text"]
    assert result[0]["title"] == "Depressive Symptoms"


# --- Psychiatry gating in the extractor ---
# These tests pin the behavior: the mental-health-exam path is gated by
# *section presence*, not by visit template. In the normal flow Nabla only
# emits the section under the psychiatry template, so section presence is a
# reliable proxy. The tests below pin both branches.


def test_default_note_without_mental_health_exam_does_not_emit_mhe_ros() -> None:
    """A non-psychiatry note (no mental_health_exam section) never produces a Mental Health Exam ROS."""
    note = ClinicalNote(
        title="Visit",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Headache"),
            NoteSection(key="history_of_present_illness", title="HPI", text="Onset 3 days ago."),
            NoteSection(
                key="review_of_systems",
                title="Review of Systems",
                text="General: No fever.\nSkin: No rash.",
            ),
        ],
    )
    proposals = extract_commands(note)
    ros_proposals = [p for p in proposals if p.command_type == "ros"]
    assert len(ros_proposals) == 1
    # Source is review_of_systems, not mental_health_exam. Use membership
    # checks (not positional) so parser-reordering doesn't flake the test.
    secs = ros_proposals[0].data["sections"]
    assert any(s["title"] == "General" for s in secs)
    assert not any(s["title"] == "Mental Health Exam" for s in secs)
    # No title or key carries "Mental Health Exam" content.
    assert not any(s["key"].startswith("mental_health") for s in secs)


def test_note_without_any_ros_section_emits_no_ros_command() -> None:
    """A note that lacks both review_of_systems and mental_health_exam yields no ROS proposal."""
    note = ClinicalNote(
        title="Visit",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Headache"),
            NoteSection(key="plan", title="Plan", text="Naproxen 500 mg."),
        ],
    )
    proposals = extract_commands(note)
    ros_proposals = [p for p in proposals if p.command_type == "ros"]
    assert ros_proposals == []


def test_mental_health_exam_routes_to_mse_command_under_psych_gate() -> None:
    """Mental_health_exam routes to a mental_status_exam command when the psychiatry gate is on.

    Belt-and-braces: section presence alone no longer routes — the caller must
    also pass ``is_psychiatry=True``. This prevents debug PUTs or template
    contract changes from leaking psych routing into non-psych visits.
    """
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="mental_health_exam",
                title="Mental Health Exam",
                text="Depressive Symptoms: Persistent low mood.\nAnxiety Symptoms: Mild.",
            ),
        ],
    )
    proposals = extract_commands(note, is_psychiatry=True)
    mse_proposals = [p for p in proposals if p.command_type == "mental_status_exam"]
    assert len(mse_proposals) == 1
    titles = [s["title"] for s in mse_proposals[0].data["sections"]]
    assert "Depressive Symptoms" in titles
    assert "Anxiety Symptoms" in titles
    assert not [p for p in proposals if p.command_type == "ros"]


def test_extract_ros_ignores_mental_health_exam_when_not_psychiatry() -> None:
    """Psych section present but visit-template not psychiatry → route through review_of_systems.

    Without the template gate, an injected mental_health_exam section
    (e.g. via debug PUT or future Nabla contract change) would leak psych
    routing into a non-psych visit. The gate forces a fallback to the
    standard review_of_systems path.
    """
    note = ClinicalNote(
        title="Subsequent Visit",
        sections=[
            NoteSection(
                key="mental_health_exam",
                title="Mental Health Exam",
                text="Depressive Symptoms: Denied.\nAnxiety Symptoms: Denied.",
            ),
            NoteSection(
                key="review_of_systems",
                title="Review of Systems",
                text="General: No fever.\nSkin: No rash.",
            ),
        ],
    )
    # is_psychiatry defaults to False — emulates a "Subsequent Visit" template.
    proposals = extract_commands(note)
    ros_proposals = [p for p in proposals if p.command_type == "ros"]
    assert len(ros_proposals) == 1
    titles = [s["title"] for s in ros_proposals[0].data["sections"]]
    # ROS routes through review_of_systems, not mental_health_exam.
    assert "General" in titles
    assert "Skin" in titles
    assert "Depressive Symptoms" not in titles
    assert "Anxiety Symptoms" not in titles


def test_extract_separates_ros_and_mse_when_psychiatry() -> None:
    """Belt-and-braces gate: under is_psychiatry=True the same payload yields a baseline
    ROS (from review_of_systems) AND a separate MSE (from mental_health_exam)."""
    note = ClinicalNote(
        title="Psychiatry",
        sections=[
            NoteSection(
                key="mental_health_exam",
                title="Mental Health Exam",
                text="Depressive Symptoms: Denied.\nAnxiety Symptoms: Denied.",
            ),
            NoteSection(
                key="review_of_systems",
                title="Review of Systems",
                text="General: No fever.\nSkin: No rash.",
            ),
        ],
    )
    proposals = extract_commands(note, is_psychiatry=True)

    ros_proposals = [p for p in proposals if p.command_type == "ros"]
    assert len(ros_proposals) == 1
    ros_titles = [s["title"] for s in ros_proposals[0].data["sections"]]
    assert "General" in ros_titles
    assert "Depressive Symptoms" not in ros_titles

    mse_proposals = [p for p in proposals if p.command_type == "mental_status_exam"]
    assert len(mse_proposals) == 1
    mse_titles = [s["title"] for s in mse_proposals[0].data["sections"]]
    assert "Depressive Symptoms" in mse_titles
    assert "General" not in mse_titles
