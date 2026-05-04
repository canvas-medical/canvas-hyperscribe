from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.custom_command import CustomCommand
from canvas_sdk.templates import render_to_string

from hyperscribe.scribe.commands.base import CommandParser


class PhysicalExamParser(CommandParser):
    command_type = "physical_exam"
    data_field = None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        # Strip the **emphasis** markers used by the Scribe UI for positive
        # findings — the chart renders the stored HTML as-is, so leaving them
        # would surface literal asterisks in the post-insert command body.
        sections = [
            {"title": s.get("title", ""), "text": (s.get("text", "") or "").replace("**", "")}
            for s in data.get("sections", [])
        ]
        html = render_to_string("scribe/templates/ros_sections.html", {"sections": sections}) or ""
        html = html.encode("ascii", "xmlcharrefreplace").decode("ascii")
        return CustomCommand(
            schema_key="physicalExam",
            content=html,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
