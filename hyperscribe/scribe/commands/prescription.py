from __future__ import annotations

from decimal import Decimal
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.constants import ClinicalQuantity

from hyperscribe.scribe.commands.base import CommandParser


class PrescriptionParser(CommandParser):
    command_type = "prescribe"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand:
        quantity = None
        raw_qty = data.get("quantity_to_dispense")
        if raw_qty is not None and raw_qty != "":
            try:
                quantity = Decimal(str(raw_qty))
            except (ValueError, ArithmeticError):
                pass

        substitutions = None
        raw_sub = data.get("substitutions")
        if raw_sub == "allowed":
            substitutions = PrescribeCommand.Substitutions.ALLOWED
        elif raw_sub == "not_allowed":
            substitutions = PrescribeCommand.Substitutions.NOT_ALLOWED

        type_to_dispense = None
        raw_type = data.get("type_to_dispense")
        if raw_type:
            representative_ndc = data.get("representative_ndc") or ""
            type_to_dispense = ClinicalQuantity(
                representative_ndc=representative_ndc,
                ncpdp_quantity_qualifier_code=raw_type,
            )

        return PrescribeCommand(
            fdb_code=data.get("fdb_code") or None,
            sig=str(data.get("sig", "")),
            days_supply=int(data["days_supply"]) if data.get("days_supply") else None,
            quantity_to_dispense=quantity,
            type_to_dispense=type_to_dispense,
            refills=int(data["refills"]) if data.get("refills") else None,
            substitutions=substitutions,
            note_to_pharmacist=data.get("note_to_pharmacist") or None,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )
