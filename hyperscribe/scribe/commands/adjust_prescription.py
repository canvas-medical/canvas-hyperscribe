from __future__ import annotations

from decimal import Decimal
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.commands.commands.adjust_prescription import AdjustPrescriptionCommand
from canvas_sdk.commands.commands.prescribe import PrescribeCommand
from canvas_sdk.commands.constants import ClinicalQuantity
from canvas_sdk.effects import Effect
from canvas_sdk.v1.data.medication import Medication, Status
from canvas_sdk.v1.data.note import Note

from hyperscribe.scribe.commands._rx_validation import validate_rx_payload
from hyperscribe.scribe.commands.base import CommandParser


class AdjustPrescriptionParser(CommandParser):
    """Parser for adjust prescription commands — uses AdjustPrescriptionCommand."""

    command_type = "adjust_prescription"
    data_field = None

    def extract(self, text: str) -> None:
        return None

    def validate(self, data: dict[str, Any]) -> list[str]:
        # adjust_prescription requires the source medication's fdb_code
        # (the existing prescription being adjusted) AND optionally a
        # ``new_fdb_code`` if the user is swapping to a different medication.
        return validate_rx_payload(
            data,
            require_fdb_code=True,
            allow_change_medication_to=True,
        )

    def validate_against_patient(self, data: dict[str, Any], note_uuid: str) -> list[str]:
        """Verify the source ``fdb_code`` resolves to an active patient medication.

        ``AdjustPrescriptionCommand`` inherits from ``RefillCommand``, which
        runs this same check during ``review()`` and raises ``ValidationError``.
        Catching it here gives a much clearer error than the generic
        ``"Medication with fdb_code X does not exist."`` from the SDK and
        keeps a half-applied ``ORIGINATE`` from getting committed.

        This is a database-touching check, so it lives outside ``validate()``
        and is only invoked by ``validate_proposals_with_note`` paths.
        """
        errors: list[str] = []
        fdb_code = (data.get("fdb_code") or "").strip()
        if not fdb_code:
            return errors
        try:
            patient_id = Note.objects.values_list("patient__id", flat=True).get(id=note_uuid)
        except Note.DoesNotExist:
            errors.append("Note not found; cannot verify the source medication")
            return errors
        if not patient_id:
            errors.append("Note has no patient; cannot verify the source medication")
            return errors
        if not (
            Medication.objects.committed()
            .for_patient(patient_id)
            .filter(status=Status.ACTIVE, codings__code=fdb_code)
            .exists()
        ):
            errors.append(
                "The selected medication is not active on this patient — "
                "adjust prescription requires an existing active medication"
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

        return AdjustPrescriptionCommand(
            new_fdb_code=data.get("new_fdb_code") or None,
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
        """Adjust prescriptions require originate + review (same as prescriptions)."""
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
