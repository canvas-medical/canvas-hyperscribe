from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.custom_command import CustomCommand

from hyperscribe.scribe.commands.base import CommandParser

_TITLE_MAP: dict[str, str] = {
    "current_medications": "Current Medications",
    "allergies": "Allergies",
    "immunizations": "Immunizations",
}


def _sections_to_html(sections: list[dict[str, str]]) -> str:
    """Render chart review subsections as HTML for the CustomCommand content."""
    parts: list[str] = []
    for i, section in enumerate(sections):
        title = section.get("title") or _TITLE_MAP.get(section.get("key", ""), "")
        text = section.get("text", "")
        if i > 0:
            parts.append("<hr>")
        parts.append(f"<h4>{title}</h4>")
        parts.append(f"<p>{text}</p>")
    return "".join(parts)


class ChartReviewParser(CommandParser):
    command_type = "chart_review"
    data_field = None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        sections: list[dict[str, str]] = data.get("sections", [])
        html = _sections_to_html(sections)
        return CustomCommand(
            schema_key="chartReview",
            content=html,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
