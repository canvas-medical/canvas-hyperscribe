from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    NoteSection,
    Transcript,
    TranscriptItem,
)
from hyperscribe.scribe.recommendations.task import (
    TaskRecommender,
    _build_user_prompt,
    extract_window_items,
    find_task_matches,
    format_transcript_windows,
    merge_windows,
)


# ── Helpers ──────────────────────────────────────────────────────────────


def _item(text: str, speaker: str, start_ms: int, end_ms: int) -> TranscriptItem:
    return TranscriptItem(text=text, speaker=speaker, start_offset_ms=start_ms, end_offset_ms=end_ms)


def _transcript(items: list[TranscriptItem]) -> Transcript:
    return Transcript(items=items)


def _make_note(sections: list[NoteSection] | None = None) -> ClinicalNote:
    return ClinicalNote(title="Test Note", sections=sections or [])


def _make_client(response_data: dict | None = None, code: HTTPStatus = HTTPStatus.OK) -> MagicMock:
    client = MagicMock()
    if response_data is not None:
        client.request.return_value = LlmResponse(
            code=code,
            response=json.dumps(response_data),
            tokens=LlmTokens(prompt=100, generated=50),
        )
    return client


# ── find_task_matches ────────────────────────────────────────────────────


def test_find_task_matches_basic() -> None:
    t = _transcript(
        [
            _item("I have a headache", "patient", 0, 2000),
            _item("Let's schedule a follow up", "provider", 3000, 5000),
            _item("Sounds good", "patient", 6000, 7000),
            _item("We also need to add a task for labs", "provider", 8000, 10000),
        ]
    )
    matches = find_task_matches(t)
    assert matches == [4000, 9000]


def test_find_task_matches_no_matches() -> None:
    t = _transcript(
        [
            _item("Hello", "provider", 0, 1000),
            _item("Hi doctor", "patient", 1500, 2500),
        ]
    )
    assert find_task_matches(t) == []


def test_find_task_matches_case_insensitive() -> None:
    t = _transcript(
        [
            _item("FOLLOW UP in two weeks", "provider", 0, 2000),
            _item("Schedule that please", "provider", 3000, 4000),
        ]
    )
    matches = find_task_matches(t)
    assert len(matches) == 2


def test_find_task_matches_hyphenated() -> None:
    t = _transcript(
        [
            _item("We need a follow-up", "provider", 0, 2000),
        ]
    )
    assert len(find_task_matches(t)) == 1


def test_find_task_matches_todo_variant() -> None:
    t = _transcript(
        [
            _item("Add that to the to-do list", "provider", 0, 2000),
        ]
    )
    assert len(find_task_matches(t)) == 1


# ── merge_windows ────────────────────────────────────────────────────────


def test_merge_windows_no_overlap() -> None:
    result = merge_windows([60_000, 360_000])
    assert result == [(0, 180_000), (240_000, 480_000)]


def test_merge_windows_overlap() -> None:
    result = merge_windows([100_000, 150_000])
    assert len(result) == 1
    assert result[0] == (0, 270_000)


def test_merge_windows_all_overlap() -> None:
    result = merge_windows([60_000, 90_000, 120_000])
    assert len(result) == 1


def test_merge_windows_empty() -> None:
    assert merge_windows([]) == []


def test_merge_windows_clamps_to_zero() -> None:
    result = merge_windows([30_000])
    assert result[0][0] == 0


# ── extract_window_items ─────────────────────────────────────────────────


def test_extract_window_items_basic() -> None:
    t = _transcript(
        [
            _item("a", "p", 0, 1000),
            _item("b", "p", 50_000, 51_000),
            _item("c", "p", 200_000, 201_000),
        ]
    )
    windows = [(0, 60_000), (190_000, 210_000)]
    result = extract_window_items(t, windows)
    assert len(result) == 2
    assert len(result[0]) == 2  # a and b overlap with first window
    assert len(result[1]) == 1  # c overlaps with second window


def test_extract_window_items_boundary() -> None:
    t = _transcript(
        [
            _item("edge", "p", 60_000, 60_001),
        ]
    )
    windows = [(0, 60_000)]
    result = extract_window_items(t, windows)
    assert len(result[0]) == 1  # item starts at window end boundary


# ── format_transcript_windows ────────────────────────────────────────────


def test_format_transcript_windows_basic() -> None:
    items = [
        [
            _item("Let's follow up", "provider", 180_000, 182_000),
            _item("OK doctor", "patient", 183_000, 184_000),
        ],
    ]
    result = format_transcript_windows(items)
    assert "[Window 1: 3:00 - 3:04]" in result
    assert "Provider: Let's follow up" in result
    assert "Patient: OK doctor" in result


def test_format_transcript_windows_empty_items() -> None:
    assert format_transcript_windows([[]]) == ""


def test_format_transcript_windows_multiple_windows() -> None:
    items = [
        [_item("first window", "provider", 0, 1000)],
        [_item("second window", "provider", 300_000, 301_000)],
    ]
    result = format_transcript_windows(items)
    assert "[Window 1:" in result
    assert "[Window 2:" in result


# ── _build_user_prompt ───────────────────────────────────────────────────


def test_build_user_prompt_includes_windows_and_note() -> None:
    note = _make_note(
        [
            NoteSection(key="hpi", title="HPI", text="Patient complains of headache."),
            NoteSection(key="plan", title="Plan", text="Follow up in 2 weeks."),
        ]
    )
    result = _build_user_prompt("Provider: follow up in 2 weeks", note)
    assert "Transcript Windows" in result
    assert "follow up in 2 weeks" in result
    assert "## HPI" in result
    assert "## Plan" in result


def test_build_user_prompt_skips_empty_sections() -> None:
    note = _make_note(
        [
            NoteSection(key="hpi", title="HPI", text="Content here."),
            NoteSection(key="ros", title="ROS", text="  "),
        ]
    )
    result = _build_user_prompt("window text", note)
    assert "## HPI" in result
    assert "## ROS" not in result


# ── TaskRecommender.recommend ────────────────────────────────────────────


def test_recommend_extracts_tasks() -> None:
    t = _transcript(
        [
            _item("Let's schedule a follow-up in two weeks", "provider", 60_000, 62_000),
        ]
    )
    note = _make_note([NoteSection(key="plan", title="Plan", text="Follow up in 2 weeks.")])
    client = _make_client(
        {
            "tasks": [
                {
                    "title": "Schedule follow-up in 2 weeks",
                    "dueDateHint": "2 weeks",
                    "assigneeHint": None,
                    "comment": None,
                    "reason": "Provider said: 'Let's schedule a follow-up in two weeks'",
                }
            ]
        }
    )

    proposals = TaskRecommender().recommend(note, client, transcript=t)

    assert len(proposals) == 1
    assert proposals[0].command_type == "task"
    assert proposals[0].display == "Schedule follow-up in 2 weeks"
    assert proposals[0].data["title"] == "Schedule follow-up in 2 weeks"
    assert proposals[0].data["due_date_hint"] == "2 weeks"
    assert proposals[0].data["reason"] == "Provider said: 'Let's schedule a follow-up in two weeks'"
    assert proposals[0].data["due_date"] is None
    assert proposals[0].data["assign_to"] is None
    assert proposals[0].section_key == "_recommended"


def test_recommend_multiple_tasks() -> None:
    t = _transcript(
        [
            _item("Schedule follow-up", "provider", 60_000, 62_000),
            _item("Also remind me to call the patient", "provider", 300_000, 302_000),
        ]
    )
    note = _make_note([NoteSection(key="plan", title="Plan", text="Follow up.")])
    client = _make_client(
        {
            "tasks": [
                {"title": "Schedule follow-up", "reason": "transcript excerpt 1"},
                {"title": "Call patient with results", "reason": "transcript excerpt 2"},
            ]
        }
    )

    proposals = TaskRecommender().recommend(note, client, transcript=t)
    assert len(proposals) == 2
    assert proposals[0].display == "Schedule follow-up"
    assert proposals[1].display == "Call patient with results"


def test_recommend_no_transcript() -> None:
    note = _make_note()
    client = _make_client()
    assert TaskRecommender().recommend(note, client, transcript=None) == []
    client.request.assert_not_called()


def test_recommend_empty_transcript() -> None:
    note = _make_note()
    client = _make_client()
    assert TaskRecommender().recommend(note, client, transcript=_transcript([])) == []
    client.request.assert_not_called()


def test_recommend_no_keywords() -> None:
    t = _transcript(
        [
            _item("Hello how are you", "provider", 0, 2000),
            _item("Fine thanks", "patient", 3000, 4000),
        ]
    )
    note = _make_note()
    client = _make_client()
    assert TaskRecommender().recommend(note, client, transcript=t) == []
    client.request.assert_not_called()


def test_recommend_llm_error() -> None:
    t = _transcript([_item("Schedule a follow-up", "provider", 0, 2000)])
    note = _make_note([NoteSection(key="plan", title="Plan", text="Follow up.")])
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response="Server error",
        tokens=LlmTokens(prompt=0, generated=0),
    )
    assert TaskRecommender().recommend(note, client, transcript=t) == []


def test_recommend_llm_exception() -> None:
    t = _transcript([_item("Schedule a follow-up", "provider", 0, 2000)])
    note = _make_note([NoteSection(key="plan", title="Plan", text="Follow up.")])
    client = MagicMock()
    client.request.side_effect = Exception("Network error")
    assert TaskRecommender().recommend(note, client, transcript=t) == []


def test_recommend_malformed_response() -> None:
    t = _transcript([_item("Schedule a follow-up", "provider", 0, 2000)])
    note = _make_note([NoteSection(key="plan", title="Plan", text="Follow up.")])
    client = MagicMock()
    client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response="not valid json",
        tokens=LlmTokens(prompt=100, generated=50),
    )
    assert TaskRecommender().recommend(note, client, transcript=t) == []


def test_recommend_empty_tasks() -> None:
    t = _transcript([_item("Schedule a follow-up", "provider", 0, 2000)])
    note = _make_note([NoteSection(key="plan", title="Plan", text="Follow up.")])
    client = _make_client({"tasks": []})
    assert TaskRecommender().recommend(note, client, transcript=t) == []


def test_recommend_skips_blank_titles() -> None:
    t = _transcript([_item("Schedule a follow-up", "provider", 0, 2000)])
    note = _make_note([NoteSection(key="plan", title="Plan", text="Follow up.")])
    client = _make_client(
        {
            "tasks": [
                {"title": "  ", "reason": "some context"},
                {"title": "Real task", "reason": "some context"},
            ]
        }
    )
    proposals = TaskRecommender().recommend(note, client, transcript=t)
    assert len(proposals) == 1
    assert proposals[0].display == "Real task"


def test_recommend_with_assignee_and_comment() -> None:
    t = _transcript([_item("Have the front desk schedule a follow-up", "provider", 0, 2000)])
    note = _make_note([NoteSection(key="plan", title="Plan", text="Follow up.")])
    client = _make_client(
        {
            "tasks": [
                {
                    "title": "Schedule follow-up",
                    "assigneeHint": "front desk",
                    "comment": "Patient prefers mornings",
                    "reason": "Provider mentioned front desk",
                }
            ]
        }
    )
    proposals = TaskRecommender().recommend(note, client, transcript=t)
    assert proposals[0].data["assignee_hint"] == "front desk"
    assert proposals[0].data["comment"] == "Patient prefers mornings"
