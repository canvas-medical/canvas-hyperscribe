from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.custom_command import CustomCommand
from canvas_sdk.templates import render_to_string

from hyperscribe.scribe.commands.base import CommandParser

_TITLE_MAP: dict[str, str] = {
    "current_medications": "Current Medications",
    "allergies": "Allergies",
    "immunizations": "Immunizations",
}


def _prepare_sections(sections: list[dict[str, str]]) -> list[dict[str, str]]:
    """Ensure each section has a title, falling back to _TITLE_MAP."""
    return [
        {
            "title": s.get("title") or _TITLE_MAP.get(s.get("key", ""), ""),
            "text": s.get("text", ""),
        }
        for s in sections
    ]


class ChartReviewParser(CommandParser):
    command_type = "chart_review"
    data_field = None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        sections = _prepare_sections(data.get("sections", []))
        html = render_to_string("scribe/templates/review_sections.html", {"sections": sections})
        return CustomCommand(
            schema_key="chartReview",
            content=html,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
