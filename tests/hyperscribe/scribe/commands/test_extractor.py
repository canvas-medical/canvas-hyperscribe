from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection
from hyperscribe.scribe.commands.extractor import extract_commands


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


def test_physical_exam_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="physical_exam", title="Physical Exam", text="Normal gait.")],
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
            NoteSection(key="assessment_and_plan", title="Assessment & Plan", text="Migraine. Start sumatriptan 50mg."),
            NoteSection(key="current_medications", title="Meds", text="- Aspirin 81mg"),
        ],
    )
    proposals = extract_commands(note)
    types = [p.command_type for p in proposals]
    assert types == ["rfv", "hpi", "vitals", "plan", "chart_review"]


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
    assert proposals[0].display == "Meds | Allergies | Immunizations"


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
