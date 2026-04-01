from __future__ import annotations

import re
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.custom_command import CustomCommand

from hyperscribe.scribe.commands.base import CommandParser


def _to_ascii_html(text: str) -> str:
    """Convert non-ASCII characters to HTML entities so they survive JSON serialization."""
    return "".join(c if ord(c) < 128 else f"&#{ord(c)};" for c in text)


def _narrative_to_html(text: str) -> str:
    """Convert lab results narrative text into structured HTML."""
    # Split on "- " at the start of items (handles both newline-separated and inline).
    items = [item.strip() for item in re.split(r"\s*-\s+", text) if item.strip()]
    if not items:
        return f"<p>{_to_ascii_html(text)}</p>"
    return "<ul>" + "".join(f"<li>{_to_ascii_html(item)}</li>" for item in items) + "</ul>"


class LabResultsParser(CommandParser):
    command_type = "lab_results"
    data_field = "narrative"

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        narrative = str(data.get("narrative", ""))
        html = _narrative_to_html(narrative) if narrative else ""
        return CustomCommand(
            schema_key="labResult",
            content=html,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
