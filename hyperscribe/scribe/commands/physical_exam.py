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
        sections = [{"title": s.get("title", ""), "text": s.get("text", "")} for s in data.get("sections", [])]
        html = render_to_string("scribe/templates/ros_sections.html", {"sections": sections})
        return CustomCommand(
            schema_key="physicalExam",
            content=html,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
