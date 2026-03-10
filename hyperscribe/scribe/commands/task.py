from __future__ import annotations

from datetime import date
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.task import AssigneeType, TaskAssigner, TaskCommand

from hyperscribe.scribe.commands.base import CommandParser


class TaskParser(CommandParser):
    command_type = "task"
    data_field = "title"

    def build(self, data: dict[str, Any], note_uuid: str) -> _BaseCommand:
        assign_to: TaskAssigner | None = None
        raw_assign = data.get("assign_to")
        if raw_assign and raw_assign.get("to"):
            assign_to = TaskAssigner(
                to=AssigneeType(raw_assign["to"]),
                **({} if raw_assign.get("id") is None else {"id": int(raw_assign["id"])}),
            )

        due_date: date | None = None
        raw_due = data.get("due_date")
        if raw_due:
            due_date = date.fromisoformat(raw_due)

        return TaskCommand(
            title=str(data.get("title", "")),
            due_date=due_date,
            assign_to=assign_to,
            note_uuid=note_uuid,
        )
