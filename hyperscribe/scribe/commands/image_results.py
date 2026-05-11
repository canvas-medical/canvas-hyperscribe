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
    """Convert image results narrative text into structured HTML.

    Lines starting with ``- `` become bullet items in a ``<ul>``. Consecutive
    non-bullet lines collapse into a single ``<p>`` with ``<br>`` between
    lines. A blank line starts a new block, so the user's paragraph breaks
    survive into the chart-rendered view.
    """
    blocks = re.split(r"\n\s*\n+", text)
    parts: list[str] = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        i = 0
        while i < len(lines):
            if lines[i].startswith("- "):
                bullets: list[str] = []
                while i < len(lines) and lines[i].startswith("- "):
                    bullets.append(lines[i][2:].strip())
                    i += 1
                parts.append(
                    "<ul>" + "".join(f"<li>{_to_ascii_html(b)}</li>" for b in bullets) + "</ul>"
                )
            else:
                paragraph: list[str] = []
                while i < len(lines) and not lines[i].startswith("- "):
                    paragraph.append(_to_ascii_html(lines[i]))
                    i += 1
                parts.append("<p>" + "<br>".join(paragraph) + "</p>")
    return "".join(parts)


class ImageResultsParser(CommandParser):
    command_type = "imaging_results"
    data_field = "narrative"

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        narrative = str(data.get("narrative", ""))
        html = _narrative_to_html(narrative) if narrative else ""
        return CustomCommand(
            schema_key="imageResult",
            content=html,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
