import inspect

from hyperscribe.scribe.backend import (
    ClinicalNote,
    CodingEntry,
    Condition,
    NormalizedData,
    NoteSection,
    Observation,
    PatientContext,
    Transcript,
    TranscriptItem,
)


def _has_init_params(cls: type, expected: dict[str, str]) -> bool:
    """Check that cls.__init__ accepts the expected keyword parameters with matching annotations."""
    sig = inspect.signature(cls.__init__)
    params = {
        name: p.annotation if isinstance(p.annotation, str) else p.annotation.__name__
        for name, p in sig.parameters.items()
        if name != "self"
    }
    if params != expected:
        print(f"Expected {expected}, got {params}")
        return False
    return True


def test_transcript_item_fields() -> None:
    assert _has_init_params(
        TranscriptItem,
        {
            "text": "str",
            "speaker": "str",
            "start_offset_ms": "int",
            "end_offset_ms": "int",
            "item_id": "str",
            "is_final": "bool",
        },
    )


def test_transcript_item_defaults() -> None:
    item = TranscriptItem(text="hi", speaker="patient", start_offset_ms=0, end_offset_ms=100)
    assert item.item_id == ""
    assert item.is_final is True


def test_transcript_item_with_new_fields() -> None:
    item = TranscriptItem(
        text="hello",
        speaker="practitioner",
        start_offset_ms=0,
        end_offset_ms=500,
        item_id="item-1",
        is_final=False,
    )
    assert item.item_id == "item-1"
    assert item.is_final is False


def test_transcript_item_equality() -> None:
    a = TranscriptItem(text="hi", speaker="patient", start_offset_ms=0, end_offset_ms=100)
    b = TranscriptItem(text="hi", speaker="patient", start_offset_ms=0, end_offset_ms=100)
    c = TranscriptItem(text="bye", speaker="patient", start_offset_ms=0, end_offset_ms=100)
    assert a == b
    assert a != c


def test_transcript_default_empty() -> None:
    transcript = Transcript()
    assert transcript.items == []


def test_clinical_note_default_empty() -> None:
    note = ClinicalNote(title="test")
    assert note.sections == []


def test_normalized_data_default_empty() -> None:
    data = NormalizedData()
    assert data.conditions == []
    assert data.observations == []


def test_patient_context_default_empty() -> None:
    ctx = PatientContext(name="Jane", birth_date="1990-01-01", gender="female")
    assert ctx.encounter_diagnoses == []


def test_note_section_fields() -> None:
    section = NoteSection(key="s", title="Subjective", text="content")
    assert section.key == "s"
    assert section.title == "Subjective"
    assert section.text == "content"


def test_coding_entry_fields() -> None:
    entry = CodingEntry(system="icd10", code="J06.9", display="URI")
    assert entry.system == "icd10"
    assert entry.code == "J06.9"
    assert entry.display == "URI"


def test_condition_fields() -> None:
    cond = Condition(display="Headache", clinical_status="active")
    assert cond.display == "Headache"
    assert cond.clinical_status == "active"
    assert cond.coding == []


def test_observation_fields() -> None:
    obs = Observation(display="BP", value="120/80", unit="mmHg")
    assert obs.display == "BP"
    assert obs.value == "120/80"
    assert obs.unit == "mmHg"
    assert obs.coding == []
