from tests.helper import is_dataclass

from hyperscribe.scribe.models import (
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


def test_transcript_item_fields():
    assert is_dataclass(
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


def test_transcript_item_defaults():
    item = TranscriptItem(text="hi", speaker="patient", start_offset_ms=0, end_offset_ms=100)
    assert item.item_id == ""
    assert item.is_final is True


def test_transcript_item_with_new_fields():
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


def test_transcript_fields():
    assert is_dataclass(Transcript, {"items": "list[TranscriptItem]"})


def test_note_section_fields():
    assert is_dataclass(NoteSection, {"key": "str", "title": "str", "text": "str"})


def test_clinical_note_fields():
    assert is_dataclass(ClinicalNote, {"title": "str", "sections": "list[NoteSection]"})


def test_coding_entry_fields():
    assert is_dataclass(CodingEntry, {"system": "str", "code": "str", "display": "str"})


def test_condition_fields():
    assert is_dataclass(
        Condition,
        {"display": "str", "clinical_status": "str", "coding": "list[CodingEntry]"},
    )


def test_observation_fields():
    assert is_dataclass(
        Observation,
        {"display": "str", "value": "str", "unit": "str", "coding": "list[CodingEntry]"},
    )


def test_normalized_data_fields():
    assert is_dataclass(
        NormalizedData,
        {"conditions": "list[Condition]", "observations": "list[Observation]"},
    )


def test_patient_context_fields():
    assert is_dataclass(
        PatientContext,
        {
            "name": "str",
            "birth_date": "str",
            "gender": "str",
            "encounter_diagnoses": "list[CodingEntry]",
        },
    )


def test_transcript_item_frozen():
    item = TranscriptItem(text="hi", speaker="patient", start_offset_ms=0, end_offset_ms=100)
    try:
        item.text = "bye"  # type: ignore[misc]
        assert False, "should be frozen"
    except AttributeError:
        pass


def test_transcript_default_empty():
    transcript = Transcript()
    assert transcript.items == []


def test_clinical_note_default_empty():
    note = ClinicalNote(title="test")
    assert note.sections == []


def test_normalized_data_default_empty():
    data = NormalizedData()
    assert data.conditions == []
    assert data.observations == []


def test_patient_context_default_empty():
    ctx = PatientContext(name="Jane", birth_date="1990-01-01", gender="female")
    assert ctx.encounter_diagnoses == []
