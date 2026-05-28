from __future__ import annotations

from decimal import Decimal
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.commands.refill import RefillCommand
from canvas_sdk.commands.constants import ClinicalQuantity
from canvas_sdk.effects import Effect
from canvas_sdk.v1.data.medication import Medication, Status
from canvas_sdk.v1.data.note import Note

from hyperscribe.scribe.commands._rx_validation import validate_rx_payload
from hyperscribe.scribe.commands.base import CommandParser


class RefillParser(CommandParser):
    """Parser for refill commands — uses RefillCommand (validates FDB against active meds)."""

    command_type = "refill"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def validate(self, data: dict[str, Any]) -> list[str]:
        return validate_rx_payload(data, require_fdb_code=True)

    def validate_against_patient(self, data: dict[str, Any], note_uuid: str) -> list[str]:
        """Verify ``fdb_code`` resolves to an active medication on the patient.

        ``RefillCommand`` runs this same check during ``review()`` and raises
        ``ValidationError`` from the SDK. Catching it here keeps the
        originate-then-fail-on-review pattern from corrupting the audit log.
        """
        errors: list[str] = []
        fdb_code = (data.get("fdb_code") or "").strip()
        if not fdb_code:
            return errors
        try:
            patient_id = (
                Note.objects.values_list("patient_id", flat=True).get(id=note_uuid)
            )
        except Note.DoesNotExist:
            errors.append("Note not found; cannot verify the medication")
            return errors
        if not patient_id:
            errors.append("Note has no patient; cannot verify the medication")
            return errors
        if not (
            Medication.objects.committed()
            .for_patient(patient_id)
            .filter(status=Status.ACTIVE, codings__code=fdb_code)
            .exists()
        ):
            errors.append(
                "The selected medication is not active on this patient — "
                "refill requires an existing active medication"
            )
        return errors

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
                **({"description": label} if (label := data.get("type_to_dispense_label")) else {}),
            )

        prescriber_id = self._resolve_prescriber(note_uuid)

        return RefillCommand(
            fdb_code=data.get("fdb_code") or None,
            sig=str(data.get("sig", ""))[:1000],
            days_supply=int(data["days_supply"]) if data.get("days_supply") not in (None, "") else None,
            quantity_to_dispense=quantity,
            type_to_dispense=type_to_dispense,
            refills=int(data["refills"]) if data.get("refills") is not None else None,
            substitutions=substitutions,
            # canvas-core caps note_to_pharmacist at 210 chars (Surescripts NewRx
            # wire limit); validate_rx_payload rejects longer strings before we
            # get here, so this truncation is a defense-in-depth safety net.
            note_to_pharmacist=(data.get("note_to_pharmacist") or "")[:210] or None,
            pharmacy=data.get("pharmacy") or None,
            prescriber_id=prescriber_id,
            note_uuid=note_uuid,
            command_uuid=command_uuid,
        )

    def to_effects(self, command: _BaseCommand, note_uuid: str | None = None) -> list[Effect]:
        """Refills require originate + review (same as prescriptions)."""
        return [command.originate(), command.review()]

    def post_originate_effects(self, command: _BaseCommand, proposal: dict[str, Any] | None = None) -> list[Effect]:
        return [command.review()]

    @staticmethod
    def _resolve_prescriber(note_uuid: str) -> str | None:
        try:
            provider_id: str | None = Note.objects.values_list("provider__id", flat=True).get(id=note_uuid)
            return provider_id
        except Exception:
            return None
