from __future__ import annotations

import time
import uuid
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.effects import Effect
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.adjust_prescription import AdjustPrescriptionParser
from hyperscribe.scribe.commands.allergy import AllergyParser
from hyperscribe.scribe.commands.assess import AssessParser
from hyperscribe.scribe.commands.base import CommandParser
from hyperscribe.scribe.commands.chart_review import ChartReviewParser
from hyperscribe.scribe.commands.diagnose import DiagnoseParser
from hyperscribe.scribe.commands.family_history import FamilyHistoryParser
from hyperscribe.scribe.commands.history_review import HistoryReviewParser
from hyperscribe.scribe.commands.hpi import HpiParser
from hyperscribe.scribe.commands.imaging_order import ImagingOrderParser
from hyperscribe.scribe.commands.lab_order import LabOrderParser
from hyperscribe.scribe.commands.lab_results import LabResultsParser
from hyperscribe.scribe.commands.medical_history import MedicalHistoryParser
from hyperscribe.scribe.commands.medication_statement import MedicationParser
from hyperscribe.scribe.commands.perform import PerformParser
from hyperscribe.scribe.commands.physical_exam import PhysicalExamParser
from hyperscribe.scribe.commands.plan import PlanParser
from hyperscribe.scribe.commands.prescription import PrescriptionParser
from hyperscribe.scribe.commands.questionnaire import QuestionnaireParser
from hyperscribe.scribe.commands.refer import ReferParser
from hyperscribe.scribe.commands.refill import RefillParser
from hyperscribe.scribe.commands.remove_allergy import RemoveAllergyParser
from hyperscribe.scribe.commands.resolve_condition import ResolveConditionParser
from hyperscribe.scribe.commands.rfv import RfvParser
from hyperscribe.scribe.commands.ros import RosParser
from hyperscribe.scribe.commands.stop_medication import StopMedicationParser
from hyperscribe.scribe.commands.surgical_history import SurgicalHistoryParser
from hyperscribe.scribe.commands.task import TaskParser
from hyperscribe.scribe.commands.vitals import VitalsParser


_BUILDERS: dict[str, CommandParser] = {
    "adjust_prescription": AdjustPrescriptionParser(),
    "allergy": AllergyParser(),
    "assess": AssessParser(),
    "chart_review": ChartReviewParser(),
    "diagnose": DiagnoseParser(),
    "familyHistory": FamilyHistoryParser(),
    "history_review": HistoryReviewParser(),
    "hpi": HpiParser(),
    "imaging_order": ImagingOrderParser(),
    "lab_order": LabOrderParser(),
    "lab_results": LabResultsParser(),
    "medicalHistory": MedicalHistoryParser(),
    "medication_statement": MedicationParser(),
    "perform": PerformParser(),
    "physical_exam": PhysicalExamParser(),
    "plan": PlanParser(),
    "prescribe": PrescriptionParser(),
    "questionnaire": QuestionnaireParser(),
    "refer": ReferParser(),
    "refill": RefillParser(),
    "remove_allergy": RemoveAllergyParser(),
    "resolve_condition": ResolveConditionParser(),
    "rfv": RfvParser(),
    "ros": RosParser(),
    "stop_medication": StopMedicationParser(),
    "surgicalHistory": SurgicalHistoryParser(),
    "task": TaskParser(),
    "vitals": VitalsParser(),
}


def annotate_duplicates(proposals: list[CommandProposal], note_uuid: str) -> None:
    """Delegate duplicate annotation to each command parser."""
    if not note_uuid:
        return
    try:
        note = Note.objects.select_related("patient").get(id=note_uuid)
    except Note.DoesNotExist:
        return
    for builder in _BUILDERS.values():
        builder.annotate_duplicates(proposals, note)


def validate_proposals(proposals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Validate all proposals. Returns list of {command_type, display, errors} for failures."""
    validation_errors: list[dict[str, Any]] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        errors = builder.validate(proposal.get("data", {}))
        if errors:
            validation_errors.append(
                {
                    "command_type": proposal.get("command_type", ""),
                    "display": (proposal.get("display") or "")[:80],
                    "errors": errors,
                }
            )
    return validation_errors


def build_effects(
    proposals: list[dict[str, Any]],
    note_uuid: str,
    feature_flags: dict[str, bool] | None = None,
) -> tuple[list[Effect], list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert selected command proposals into Canvas SDK Effects.

    Each command is originated individually so a single failure doesn't
    take down unrelated commands. Post-originate effects (commit/review)
    follow immediately since Canvas processes effects sequentially.

    Returns (effects, metadata_pending, attempted) where:
    - metadata_pending: items needing a second request for metadata upsert
    - attempted: list of {command_uuid, command_type, display} for verification
    """
    built: list[tuple[CommandParser, _BaseCommand, dict[str, Any]]] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        command = builder.build(proposal.get("data", {}), note_uuid, str(uuid.uuid4()))
        built.append((builder, command, proposal))

    if not built:
        return [], [], []

    effects: list[Effect] = []
    for _, command, _ in built:
        effects.append(command.originate())

    for builder, command, proposal in built:
        effects.extend(builder.post_originate_effects(command, proposal))

    metadata_pending: list[dict[str, Any]] = []
    for builder, command, proposal in built:
        meta = builder.pending_metadata(command, proposal, feature_flags)
        if meta:
            metadata_pending.append(meta)

    attempted = [
        {
            "command_uuid": str(command.command_uuid),
            "command_type": builder.command_type,
            "display": (proposal.get("display") or "")[:80],
        }
        for builder, command, proposal in built
    ]

    return effects, metadata_pending, attempted


_METADATA_DB_WAIT_ATTEMPTS = 6
_METADATA_DB_WAIT_INTERVAL_SECONDS = 0.25


def _wait_for_command(command_uuid: str) -> bool:
    """Poll the DB for the just-committed command before requesting metadata upsert.

    Phase 1 returns the originate/commit effects with the API response; Canvas
    then applies them asynchronously. The SDK's upsert_metadata runs a *synchronous*
    DB existence check at effect-build time (see canvas_sdk.effects.command_metadata.base),
    so without this wait the second request often races phase 1 and the validator
    raises before any effect leaves the plugin.
    """
    for attempt in range(_METADATA_DB_WAIT_ATTEMPTS):
        if Command.objects.filter(id=command_uuid).exists():
            if attempt > 0:
                log.info("metadata: command %s visible after %d retries", command_uuid, attempt)
            return True
        time.sleep(_METADATA_DB_WAIT_INTERVAL_SECONDS)
    return False


def build_metadata_effects(pending: list[dict[str, Any]]) -> list[Effect]:
    """Phase 2: build upsert_metadata effects for commands that now exist in the DB.

    Each item is processed defensively: if the command is not yet visible after a
    bounded wait, or if the SDK's upsert validation fails for any reason, we log
    and skip rather than 500'ing the entire batch.
    """
    effects: list[Effect] = []
    for item in pending:
        command_type = item.get("command_type", "")
        command_uuid = item.get("command_uuid", "")
        note_uuid = item.get("note_uuid", "")
        metadata = item.get("metadata", {}) or {}

        builder = _BUILDERS.get(command_type)
        if builder is None:
            log.warning("metadata: unknown command_type=%r (uuid=%s)", command_type, command_uuid)
            continue
        if not command_uuid or not metadata:
            log.warning("metadata: skipping malformed item: %r", item)
            continue

        if not _wait_for_command(command_uuid):
            log.warning(
                "metadata: command %s (%s) not visible in DB after %d attempts; skipping upsert of %s",
                command_uuid,
                command_type,
                _METADATA_DB_WAIT_ATTEMPTS,
                list(metadata.keys()),
            )
            continue

        try:
            command = builder.build_stub(command_uuid, note_uuid)
            for key, value in metadata.items():
                effects.append(command.upsert_metadata(key, value))
                log.info(
                    "metadata: queued upsert command=%s type=%s key=%s value=%s",
                    command_uuid,
                    command_type,
                    key,
                    value,
                )
        except Exception:
            log.exception(
                "metadata: upsert_metadata failed for command=%s type=%s keys=%s",
                command_uuid,
                command_type,
                list(metadata.keys()),
            )
    return effects
