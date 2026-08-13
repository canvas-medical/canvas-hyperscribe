"""Shared transcript-windowing helpers for recommenders that read the transcript.

Most recommenders extract from the Nabla-generated note. That is lossy: whatever the
summarization step omits can never be recovered downstream. When a recommender needs the
transcript as well, sending the whole thing is wasteful and dilutes the prompt, so the
pattern is to locate the relevant moments by keyword and send only those windows.

``TaskRecommender`` established this pattern; these helpers are the vendor- and
domain-neutral parts of it, factored out so other recommenders can reuse them.
"""

from __future__ import annotations

import re

from hyperscribe.scribe.backend.models import NoteSection, Transcript, TranscriptItem

# Half-width of the window kept around each keyword hit. Two minutes is generous enough
# that a medication named a while before its directions still lands in the same window.
WINDOW_MS = 120_000

# As-needed / PRN phrasing, used to locate the parts of a transcript where a PRN order may
# have been dictated.
#
# Deliberately tuned for recall, not precision. This pattern only decides which transcript
# excerpts get shown to the LLM; the LLM still decides whether an excerpt actually contains
# a medication. So a false positive costs a few tokens, while a false negative reproduces
# the very bug this exists to fix. Non-medication phrases like "follow up as needed" do
# match here on purpose — they are filtered by the extraction prompt, not by this regex.
_PRN_PHRASES = [
    r"\bas[\s-]+needed\b",
    r"\bp\.?\s?r\.?\s?n\.?\b",
    r"\bwhen[\s-]+needed\b",
    r"\bif[\s-]+needed\b",
    r"\bas[\s-]+necessary\b",
    r"\bas[\s-]+required\b",
]
PRN_PATTERN = re.compile("|".join(_PRN_PHRASES), re.IGNORECASE)


def find_keyword_matches(transcript: Transcript, pattern: re.Pattern[str]) -> list[int]:
    """Return midpoint timestamps (ms) of transcript items matching ``pattern``."""
    matches: list[int] = []
    for item in transcript.items:
        if pattern.search(item.text):
            midpoint = (item.start_offset_ms + item.end_offset_ms) // 2
            matches.append(midpoint)
    return matches


def merge_windows(timestamps: list[int], window_ms: int = WINDOW_MS) -> list[tuple[int, int]]:
    """Merge overlapping [t - window, t + window] intervals."""
    if not timestamps:
        return []
    intervals = sorted((max(0, t - window_ms), t + window_ms) for t in timestamps)
    merged = [intervals[0]]
    for start, end in intervals[1:]:
        if start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def extract_window_items(transcript: Transcript, windows: list[tuple[int, int]]) -> list[list[TranscriptItem]]:
    """For each window, collect overlapping transcript items."""
    result: list[list[TranscriptItem]] = []
    for w_start, w_end in windows:
        items = [item for item in transcript.items if item.end_offset_ms >= w_start and item.start_offset_ms <= w_end]
        result.append(items)
    return result


def format_transcript_windows(window_items: list[list[TranscriptItem]]) -> str:
    """Format window items into a human-readable string for the LLM prompt."""
    parts: list[str] = []
    for i, items in enumerate(window_items, 1):
        if not items:
            continue
        start_ms = items[0].start_offset_ms
        end_ms = items[-1].end_offset_ms
        start_fmt = f"{start_ms // 60000}:{(start_ms % 60000) // 1000:02d}"
        end_fmt = f"{end_ms // 60000}:{(end_ms % 60000) // 1000:02d}"
        lines: list[str] = []
        for item in items:
            speaker = item.speaker.capitalize() if item.speaker else "Unknown"
            lines.append(f"{speaker}: {item.text}")
        parts.append(f"[Window {i}: {start_fmt} - {end_fmt}]\n" + "\n".join(lines))
    return "\n\n".join(parts)


def collect_windows(transcript: Transcript | None, pattern: re.Pattern[str]) -> str:
    """Return formatted transcript windows around every ``pattern`` hit, or "" if none.

    Convenience wrapper over the four steps above, for recommenders that only want the
    prompt-ready text.
    """
    if not transcript or not transcript.items:
        return ""
    timestamps = find_keyword_matches(transcript, pattern)
    if not timestamps:
        return ""
    return format_transcript_windows(extract_window_items(transcript, merge_windows(timestamps)))


def format_note_sections(sections: list[NoteSection]) -> str:
    """Format note sections as markdown headings for the LLM prompt."""
    return "\n\n".join(f"## {section.title}\n{section.text}" for section in sections)


def _drug_token(medication_name: str) -> str:
    """The drug word of a stated medication name, lowercased — "Lorazepam 0.5 mg" -> "lorazepam"."""
    words: list[str] = re.findall(r"[A-Za-z]{4,}", medication_name)
    return words[0].lower() if words else ""


def note_documents_as_needed(sections: list[NoteSection], medication_name: str) -> bool:
    """True when a note section already documents this drug WITH as-needed dosing.

    Used to correct the model's ``from_transcript`` claim. Asking the LLM whether an entry was
    absent from the note proved unreliable in the partial-loss case: when Nabla drops a PRN from
    CURRENT_MEDICATIONS but keeps it in ASSESSMENT_AND_PLAN, the model reports it as
    transcript-recovered even though the note still carries it.

    The test is name AND as-needed, never name alone. A drug frequently appears in the note under
    a *scheduled* order while its as-needed order is the one that went missing — the reported
    lorazepam case — and a name-only test would clear the flag on a genuine recovery.
    """
    token = _drug_token(medication_name)
    if not token:
        return False
    for section in sections:
        for line in section.text.split("\n"):
            if token in line.lower() and PRN_PATTERN.search(line):
                return True
    return False


def build_user_prompt(sections: list[NoteSection], windows_text: str = "") -> str:
    """Compose note sections plus, when supplied, the matching transcript excerpts.

    With no windows the result is exactly the note-sections-only prompt these recommenders
    sent before transcript recovery existed, so a visit with no keyword hits is unaffected.
    """
    note_text = format_note_sections(sections)
    if not windows_text:
        return note_text
    return (
        "## Clinical Note Sections\n\n"
        f"{note_text}\n\n"
        "## Transcript Excerpts (as-needed medication language detected)\n\n"
        f"{windows_text}"
    )
