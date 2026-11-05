from __future__ import annotations

import json
import re
from http import HTTPStatus

from logger import log

from canvas_sdk.clients.llms.libraries import LlmAnthropic

from hyperscribe.scribe.backend.models import (
    ClinicalNote,
    CommandProposal,
    Transcript,
)
from hyperscribe.scribe.recommendations._transcript_windows import (
    extract_window_items,
    find_keyword_matches,
    format_transcript_windows,
    merge_windows,
)
from hyperscribe.scribe.recommendations.base import BaseRecommender
from hyperscribe.scribe.recommendations.schemas import TaskRecommendationList

_TASK_KEYWORDS = [
    r"\btasks?\b",
]
_KEYWORD_PATTERN = re.compile("|".join(_TASK_KEYWORDS), re.IGNORECASE)

_SYSTEM_PROMPT = (
    "You are a clinical task extraction assistant.\n\n"
    "You are given:\n"
    "1. Transcript windows from a patient-provider encounter where task-related language was detected.\n"
    "2. The full structured clinical note for context.\n\n"
    "Extract actionable post-visit tasks for the care team. Examples:\n"
    "- Add a task to make calls (e.g. 'call patient with results')\n"
    "- Add a task to call patient with instructions\n"
    "- Add a task to check if patient is being followed by a specialty\n\n"
    "For each task, provide:\n"
    "- A clear, concise title a staff member can act on\n"
    "- due_date_hint if the provider mentioned timing (relative or absolute)\n"
    "- assignee_hint if the provider mentioned who should handle it\n"
    "- comment with any additional relevant details\n"
    "- reason: quote or closely paraphrase the specific transcript excerpt that prompted this task\n\n"
    "Do NOT extract:\n"
    "- Actions being done during the visit itself (e.g. 'let me check your blood pressure now')\n"
    "- Diagnoses or assessments (handled separately)\n"
    "- Medication changes (handled by the prescription system)\n\n"
    "If no actionable post-visit tasks are found, return an empty list."
)


def find_task_matches(transcript: Transcript) -> list[int]:
    """Return midpoint timestamps (ms) of transcript items containing task keywords."""
    return find_keyword_matches(transcript, _KEYWORD_PATTERN)


def _build_user_prompt(windows_text: str, note: ClinicalNote) -> str:
    note_parts: list[str] = []
    for section in note.sections:
        if section.text.strip():
            note_parts.append(f"## {section.title}\n{section.text}")

    return (
        "## Transcript Windows (task-related language detected)\n\n"
        f"{windows_text}\n\n"
        "## Full Clinical Note\n\n" + "\n\n".join(note_parts)
    )


class TaskRecommender(BaseRecommender):
    def recommend(
        self, note: ClinicalNote, client: LlmAnthropic, transcript: Transcript | None = None
    ) -> list[CommandProposal]:
        if not transcript or not transcript.items:
            return []

        timestamps = find_task_matches(transcript)
        if not timestamps:
            return []

        windows = merge_windows(timestamps)
        window_items = extract_window_items(transcript, windows)
        windows_text = format_transcript_windows(window_items)
        if not windows_text:
            return []

        client.reset_prompts()
        client.set_system_prompt([_SYSTEM_PROMPT])
        client.set_user_prompt([_build_user_prompt(windows_text, note)])
        client.set_schema(TaskRecommendationList)

        try:
            response = client.request()
        except Exception:
            log.exception("LLM request failed for task recommendations")
            return []

        if response.code != HTTPStatus.OK:
            log.info(f"LLM returned {response.code} for task recommendations: {response.response}")
            return []

        try:
            parsed = TaskRecommendationList.model_validate(json.loads(response.response))
        except Exception:
            log.exception(f"Failed to parse task LLM response: {response.response}")
            return []

        proposals: list[CommandProposal] = []
        for task in parsed.tasks:
            if not task.title.strip():
                continue
            proposals.append(
                CommandProposal(
                    command_type="task",
                    display=task.title.strip(),
                    data={
                        "title": task.title.strip(),
                        "due_date": None,
                        "assign_to": None,
                        "labels": None,
                        "comment": task.comment or None,
                        "due_date_hint": task.due_date_hint or None,
                        "assignee_hint": task.assignee_hint or None,
                        "reason": task.reason,
                    },
                    section_key="_recommended",
                )
            )
        return proposals
