from __future__ import annotations

import re

from hyperscribe.scribe.backend.models import NoteSection, Transcript, TranscriptItem
from hyperscribe.scribe.recommendations._transcript_windows import (
    WINDOW_MS,
    collect_windows,
    extract_window_items,
    find_keyword_matches,
    format_note_sections,
    format_transcript_windows,
    merge_windows,
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
