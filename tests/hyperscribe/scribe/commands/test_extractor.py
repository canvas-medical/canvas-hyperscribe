from hyperscribe.scribe.backend.models import ClinicalNote, NoteSection
from hyperscribe.scribe.commands.extractor import (
    _truncate,
    extract_commands,
)


def test_truncate_short_text() -> None:
    assert _truncate("hello") == "hello"


def test_truncate_long_text() -> None:
    text = "a" * 100
    result = _truncate(text)
    assert len(result) == 80
    assert result.endswith("...")


def test_truncate_exact_boundary() -> None:
    text = "a" * 80
    assert _truncate(text) == text


def test_chief_complaint_produces_rfv() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="chief_complaint",
                title="Chief Complaint",
                text="Patient presents with lower back pain.",
            ),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1

    rfv = proposals[0]
    assert rfv.command_type == "rfv"
    assert rfv.data["comment"] == "Patient presents with lower back pain."
    assert rfv.selected is True


def test_hpi_section_produces_hpi() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="history_of_present_illness",
                title="History of Present Illness",
                text="Pain radiates down left leg. Onset 2 weeks ago.",
            ),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1

    hpi = proposals[0]
    assert hpi.command_type == "hpi"
    assert hpi.data["narrative"] == "Pain radiates down left leg. Onset 2 weeks ago."
    assert hpi.selected is True


def test_plan_section_produces_plan() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(
                key="plan",
                title="Plan",
                text="Start naproxen 500mg BID. Order lumbar MRI.",
            ),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1

    plan = proposals[0]
    assert plan.command_type == "plan"
    assert plan.data["narrative"] == "Start naproxen 500mg BID. Order lumbar MRI."
    assert plan.selected is True


def test_assessment_section_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="assessment", title="Assessment", text="Lumbar disc herniation."),
        ],
    )
    assert extract_commands(note) == []


def test_objective_sections_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="vitals", title="Vitals", text="BP 120/80, HR 72"),
            NoteSection(key="physical_exam", title="Physical Exam", text="Normal gait."),
        ],
    )
    assert extract_commands(note) == []


def test_empty_sections() -> None:
    note = ClinicalNote(title="Note", sections=[])
    assert extract_commands(note) == []


def test_empty_text_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="Chief Complaint", text=""),
            NoteSection(key="plan", title="Plan", text="   "),
        ],
    )
    assert extract_commands(note) == []


def test_display_truncated() -> None:
    long_text = "Patient presents with a very long narrative. " + "x" * 200
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="Chief Complaint", text=long_text),
        ],
    )
    proposals = extract_commands(note)
    assert len(proposals) == 1
    assert len(proposals[0].display) <= 80


def test_full_multiple_sections_note() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="chief_complaint", title="Chief Complaint", text="Headaches for two weeks."),
            NoteSection(key="history_of_present_illness", title="HPI", text="Mostly right-sided."),
            NoteSection(key="vitals", title="Vitals", text="BP 130/85"),
            NoteSection(key="assessment", title="Assessment", text="Migraine."),
            NoteSection(key="plan", title="Plan", text="Start sumatriptan 50mg."),
        ],
    )
    proposals = extract_commands(note)
    types = [p.command_type for p in proposals]
    assert types == ["rfv", "hpi", "plan"]


def test_unknown_section_skipped() -> None:
    note = ClinicalNote(
        title="Note",
        sections=[
            NoteSection(key="some_custom_section", title="Custom", text="Some text here."),
        ],
    )
    assert extract_commands(note) == []
