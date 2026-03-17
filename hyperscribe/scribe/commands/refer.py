from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.refer import ReferCommand
from canvas_sdk.commands.constants import ServiceProvider

from hyperscribe.scribe.commands.base import CommandParser

CLINICAL_QUESTION_MAP = {q.value: q for q in ReferCommand.ClinicalQuestion}


class ReferParser(CommandParser):
    command_type = "refer"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        priority = None
        raw_priority = data.get("priority")
        if raw_priority == "Routine":
            priority = ReferCommand.Priority.ROUTINE
        elif raw_priority == "Urgent":
            priority = ReferCommand.Priority.URGENT

        service_provider = None
        sp_data = data.get("service_provider")
        if sp_data and isinstance(sp_data, dict):
            service_provider = ServiceProvider(
                first_name=sp_data.get("first_name") or "",
                last_name=sp_data.get("last_name") or "",
                specialty=sp_data.get("specialty") or "",
                practice_name=sp_data.get("practice_name") or "",
                business_fax=sp_data.get("business_fax"),
                business_phone=sp_data.get("business_phone"),
                business_address=sp_data.get("business_address"),
            )

        clinical_question = None
        raw_cq = data.get("clinical_question")
        if raw_cq:
            clinical_question = CLINICAL_QUESTION_MAP.get(raw_cq)

        return ReferCommand(
            service_provider=service_provider,
            diagnosis_codes=data.get("diagnosis_codes") or [],
            clinical_question=clinical_question,
            priority=priority,
            notes_to_specialist=data.get("notes_to_specialist") or None,
            comment=data.get("comment") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
