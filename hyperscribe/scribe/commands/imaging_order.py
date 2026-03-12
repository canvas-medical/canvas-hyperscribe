from __future__ import annotations

from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.imaging_order import ImagingOrderCommand
from canvas_sdk.commands.constants import ServiceProvider

from hyperscribe.scribe.commands.base import CommandParser


class ImagingOrderParser(CommandParser):
    command_type = "imaging_order"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        priority = None
        raw_priority = data.get("priority")
        if raw_priority == "Routine":
            priority = ImagingOrderCommand.Priority.ROUTINE
        elif raw_priority == "Urgent":
            priority = ImagingOrderCommand.Priority.URGENT

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

        return ImagingOrderCommand(
            image_code=data.get("image_code") or None,
            diagnosis_codes=data.get("diagnosis_codes") or None,
            additional_details=data.get("additional_details") or None,
            comment=data.get("comment") or None,
            priority=priority,
            ordering_provider_key=data.get("ordering_provider_id") or None,
            service_provider=service_provider,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
