from __future__ import annotations

import re

from hyperscribe.scribe.backend.models import NoteSection, Transcript, TranscriptItem
from hyperscribe.scribe.recommendations._transcript_windows import (
    PRN_PATTERN,
    WINDOW_MS,
    build_user_prompt,
    collect_windows,
    extract_window_items,
    find_keyword_matches,
    format_note_sections,
    format_transcript_windows,
    merge_windows,
    note_documents_as_needed,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _item(text: str, start_ms: int, end_ms: int, speaker: str = "doctor") -> TranscriptItem:
    """Build a transcript item at a fixed offset."""
    return TranscriptItem(text=text, speaker=speaker, start_offset_ms=start_ms, end_offset_ms=end_ms)


def _transcript(*items: TranscriptItem) -> Transcript:
    """Build a transcript from the given items."""
    return Transcript(items=list(items))


_PATTERN = re.compile(r"\bneedle\b", re.IGNORECASE)


# ── find_keyword_matches ─────────────────────────────────────────────────


def test_find_keyword_matches_returns_midpoints() -> None:
    """A matching item yields the midpoint of its own offsets."""
    transcript = _transcript(_item("pass me the needle", 10_000, 20_000))
    assert find_keyword_matches(transcript, _PATTERN) == [15_000]


def test_find_keyword_matches_no_matches() -> None:
    """A transcript with no pattern hit yields no timestamps."""
    transcript = _transcript(_item("nothing relevant here", 0, 1_000))
    assert find_keyword_matches(transcript, _PATTERN) == []


def test_find_keyword_matches_is_pattern_driven() -> None:
    """The caller's pattern decides matching, including its own case-insensitivity."""
    transcript = _transcript(_item("NEEDLE", 0, 2_000))
    assert find_keyword_matches(transcript, _PATTERN) == [1_000]
    assert find_keyword_matches(transcript, re.compile(r"\bneedle\b")) == []


def test_find_keyword_matches_multiple_items() -> None:
    """Every matching item contributes one timestamp, in transcript order."""
    transcript = _transcript(
        _item("needle one", 0, 2_000),
        _item("irrelevant", 3_000, 4_000),
        _item("needle two", 10_000, 12_000),
    )
    assert find_keyword_matches(transcript, _PATTERN) == [1_000, 11_000]


def test_find_keyword_matches_empty_transcript() -> None:
    """An empty transcript yields no timestamps."""
    assert find_keyword_matches(_transcript(), _PATTERN) == []


# ── merge_windows ────────────────────────────────────────────────────────


def test_merge_windows_no_overlap() -> None:
    """Timestamps further apart than 2x the window stay separate."""
    assert merge_windows([60_000, 360_000]) == [(0, 180_000), (240_000, 480_000)]


def test_merge_windows_overlap() -> None:
    """Overlapping intervals collapse into one spanning window."""
    assert merge_windows([100_000, 150_000]) == [(0, 270_000)]


def test_merge_windows_empty() -> None:
    """No timestamps yields no windows."""
    assert merge_windows([]) == []


def test_merge_windows_clamps_to_zero() -> None:
    """A window starting before the recording begins is clamped to zero."""
    assert merge_windows([30_000]) == [(0, 150_000)]


def test_merge_windows_honors_custom_width() -> None:
    """An explicit window_ms overrides the module default."""
    assert merge_windows([50_000], window_ms=1_000) == [(49_000, 51_000)]


def test_merge_windows_default_width_is_module_constant() -> None:
    """The default half-width is WINDOW_MS."""
    assert merge_windows([WINDOW_MS]) == [(0, 2 * WINDOW_MS)]


# ── extract_window_items ─────────────────────────────────────────────────


def test_extract_window_items_collects_overlapping() -> None:
    """Only items overlapping a window are collected, per window."""
    transcript = _transcript(
        _item("first", 0, 1_000),
        _item("second", 5_000, 6_000),
        _item("third", 500_000, 501_000),
    )
    result = extract_window_items(transcript, [(0, 10_000), (490_000, 510_000)])
    assert [[i.text for i in window] for window in result] == [["first", "second"], ["third"]]


def test_extract_window_items_boundary_is_inclusive() -> None:
    """An item touching a window edge is included."""
    transcript = _transcript(_item("edge", 10_000, 20_000))
    assert len(extract_window_items(transcript, [(20_000, 30_000)])[0]) == 1
    assert len(extract_window_items(transcript, [(0, 10_000)])[0]) == 1


def test_extract_window_items_window_with_no_items() -> None:
    """A window matching nothing yields an empty list, preserving window count."""
    transcript = _transcript(_item("only", 0, 1_000))
    assert extract_window_items(transcript, [(0, 500), (900_000, 910_000)]) == [[transcript.items[0]], []]


# ── format_transcript_windows ────────────────────────────────────────────


def test_format_transcript_windows_labels_speaker_and_time() -> None:
    """Each window is headed by its mm:ss range and speaker-labelled lines."""
    items = [[_item("take it as needed", 65_000, 70_000, "doctor")]]
    result = format_transcript_windows(items)
    assert result == "[Window 1: 1:05 - 1:10]\nDoctor: take it as needed"


def test_format_transcript_windows_empty_items() -> None:
    """A window with no items is skipped entirely."""
    assert format_transcript_windows([[]]) == ""


def test_format_transcript_windows_no_windows() -> None:
    """No windows yields an empty string."""
    assert format_transcript_windows([]) == ""


def test_format_transcript_windows_missing_speaker() -> None:
    """An item with no speaker is labelled Unknown."""
    items = [[_item("who said this", 0, 1_000, "")]]
    assert "Unknown: who said this" in format_transcript_windows(items)


def test_format_transcript_windows_multiple_windows_are_numbered() -> None:
    """Windows are numbered from 1 and separated by a blank line."""
    items = [[_item("one", 0, 1_000)], [_item("two", 600_000, 601_000)]]
    result = format_transcript_windows(items)
    assert "[Window 1: 0:00 - 0:01]" in result
    assert "[Window 2: 10:00 - 10:01]" in result
    assert "\n\n" in result


# ── collect_windows ──────────────────────────────────────────────────────


def test_collect_windows_end_to_end() -> None:
    """The wrapper chains match, merge, extract, and format."""
    transcript = _transcript(
        _item("bring the needle", 60_000, 62_000),
        _item("unrelated chatter", 63_000, 64_000),
    )
    result = collect_windows(transcript, _PATTERN)
    assert "Doctor: bring the needle" in result
    assert "Doctor: unrelated chatter" in result


def test_collect_windows_none_transcript() -> None:
    """A missing transcript yields an empty string rather than raising."""
    assert collect_windows(None, _PATTERN) == ""


def test_collect_windows_empty_transcript() -> None:
    """A transcript with no items yields an empty string."""
    assert collect_windows(_transcript(), _PATTERN) == ""


def test_collect_windows_no_pattern_match() -> None:
    """A transcript that never matches yields an empty string."""
    transcript = _transcript(_item("nothing to see", 0, 1_000))
    assert collect_windows(transcript, _PATTERN) == ""


# ── format_note_sections ─────────────────────────────────────────────────


def test_format_note_sections_renders_headings() -> None:
    """Sections render as markdown headings joined by a blank line."""
    sections = [
        NoteSection(key="plan", title="Plan", text="start lisinopril"),
        NoteSection(key="hpi", title="HPI", text="chest pain"),
    ]
    assert format_note_sections(sections) == "## Plan\nstart lisinopril\n\n## HPI\nchest pain"


def test_format_note_sections_empty() -> None:
    """No sections yields an empty string."""
    assert format_note_sections([]) == ""


# ── PRN_PATTERN ──────────────────────────────────────────────────────────


def test_prn_pattern_matches_as_needed_spellings() -> None:
    """The common as-needed spellings and abbreviations are all recognised."""
    for phrase in (
        "0.5 mg every four hours as needed for anxiety",
        "one tablet as-needed",
        "ibuprofen PRN",
        "lorazepam prn agitation",
        "take p.r.n.",
        "tylenol when needed",
        "use if needed",
        "another dose as necessary",
        "oxygen as required",
    ):
        assert PRN_PATTERN.search(phrase), phrase


def test_prn_pattern_is_case_insensitive() -> None:
    """Casing does not affect matching."""
    assert PRN_PATTERN.search("AS NEEDED")
    assert PRN_PATTERN.search("As Needed")


def test_prn_pattern_tolerates_extra_whitespace() -> None:
    """Transcription artifacts like doubled spaces still match."""
    assert PRN_PATTERN.search("take it as  needed")


def test_prn_pattern_ignores_unrelated_words() -> None:
    """Words merely containing the letters p, r, n do not match the PRN abbreviation."""
    for phrase in ("print the summary", "the person is stable", "prone position", "pruning"):
        assert not PRN_PATTERN.search(phrase), phrase


def test_prn_pattern_matches_non_medication_phrases_by_design() -> None:
    """Non-medication as-needed phrasing matches on purpose.

    The pattern only decides which transcript excerpts reach the LLM; the extraction prompt
    is what rejects them. Tuning for recall here is deliberate — a false negative
    reproduces the PRN loss this exists to prevent, a false positive costs a few tokens.
    """
    assert PRN_PATTERN.search("follow up as needed")
    assert PRN_PATTERN.search("call us if needed")


# ── build_user_prompt ────────────────────────────────────────────────────


def _sections() -> list[NoteSection]:
    """Two note sections for prompt assembly."""
    return [
        NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10 mg daily"),
        NoteSection(key="plan", title="Plan", text="Continue current regimen."),
    ]


def test_build_user_prompt_without_windows_is_note_only() -> None:
    """With no transcript excerpts the prompt is exactly the note-sections rendering.

    This is the no-regression guarantee for visits with no as-needed language: the prompt
    must be byte-identical to what shipped before transcript recovery existed.
    """
    sections = _sections()
    assert build_user_prompt(sections, "") == format_note_sections(sections)
    assert build_user_prompt(sections) == format_note_sections(sections)


def test_build_user_prompt_with_windows_includes_both_sources() -> None:
    """With excerpts the prompt carries both, under distinguishing headings."""
    result = build_user_prompt(_sections(), "[Window 1: 0:10 - 0:20]\nDoctor: lorazepam as needed")
    assert "## Clinical Note Sections" in result
    assert "Lisinopril 10 mg daily" in result
    assert "## Transcript Excerpts (as-needed medication language detected)" in result
    assert "Doctor: lorazepam as needed" in result


def test_build_user_prompt_windows_only() -> None:
    """Excerpts still reach the model when no note section matched."""
    result = build_user_prompt([], "[Window 1: 0:00 - 0:05]\nDoctor: morphine as needed")
    assert "Doctor: morphine as needed" in result
    assert "## Transcript Excerpts (as-needed medication language detected)" in result


# ── note_documents_as_needed ─────────────────────────────────────────────


def test_note_documents_as_needed_finds_prn_line() -> None:
    """A note line naming the drug with as-needed dosing counts as documented."""
    sections = [
        NoteSection(
            key="assessment_and_plan",
            title="A&P",
            text="Anxiety\n- Add lorazepam 0.5 mg every four hours as needed for agitation.",
        )
    ]
    assert note_documents_as_needed(sections, "Lorazepam 0.5 mg") is True


def test_note_documents_as_needed_ignores_scheduled_only_mention() -> None:
    """A scheduled order for the same drug must NOT count as documenting the PRN.

    This is the reported lorazepam case: the note keeps the scheduled pre-shower dose and loses
    the as-needed order. A name-only test would clear the flag on a genuine recovery.
    """
    sections = [
        NoteSection(
            key="current_medications",
            title="Meds",
            text="- Lorazepam, one tablet daily, one hour before showers on Mondays and Wednesdays",
        )
    ]
    assert note_documents_as_needed(sections, "Lorazepam 0.5 mg") is False


def test_note_documents_as_needed_requires_the_same_drug() -> None:
    """An as-needed line for a different drug does not count."""
    sections = [NoteSection(key="plan", title="Plan", text="- Melatonin 3 mg as needed at bedtime.")]
    assert note_documents_as_needed(sections, "Polyethylene glycol 17 grams") is False


def test_note_documents_as_needed_across_sections() -> None:
    """Any supplied section counts, not just the medication list."""
    sections = [
        NoteSection(key="current_medications", title="Meds", text="- lisinopril 10 mg once daily"),
        NoteSection(key="plan", title="Plan", text="- Albuterol inhaler, two puffs as needed for dyspnea."),
    ]
    assert note_documents_as_needed(sections, "Albuterol inhaler") is True


def test_note_documents_as_needed_unparseable_name() -> None:
    """A name with no usable drug word cannot be matched, so it is not documented."""
    assert note_documents_as_needed([NoteSection(key="plan", title="P", text="x as needed")], "5 mg") is False


def test_note_documents_as_needed_empty_sections() -> None:
    """No sections means nothing is documented."""
    assert note_documents_as_needed([], "Lorazepam 0.5 mg") is False
