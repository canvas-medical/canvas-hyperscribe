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


def test_assessment_section_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[NoteSection(key="assessment", title="Assessment", text="Lumbar disc herniation.")],
    )
    assert extract_commands(note) == []


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


def test_full_multiple_sections_note() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="CC", text="Headaches for two weeks."),
            NoteSection(key="history_of_present_illness", title="HPI", text="Mostly right-sided."),
            NoteSection(key="vitals", title="Vitals", text="BP 130/85"),
            NoteSection(key="assessment", title="Assessment", text="Migraine."),
            NoteSection(key="plan", title="Plan", text="Start sumatriptan 50mg."),
        ],
    )
    proposals = extract_commands(note)
    types = [p.command_type for p in proposals]
    assert types == ["rfv", "hpi", "vitals", "plan"]
