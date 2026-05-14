from __future__ import annotations

import logging
import uuid
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.effects import Effect
from canvas_sdk.v1.data.note import Note

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

log = logging.getLogger(__name__)


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


def validate_proposals(
    proposals: list[dict[str, Any]],
    note_uuid: str | None = None,
) -> list[dict[str, Any]]:
    """Validate all proposals. Returns list of {command_type, display, errors} for failures.

    When ``note_uuid`` is supplied, parsers that implement
    ``validate_against_patient`` also get a chance to verify chart state
    (e.g. that a refill/adjust_prescription's ``fdb_code`` resolves to an
    active medication on the note's patient). The DB-touching validation is
    skipped when ``note_uuid`` is None or empty so unit tests can call this
    function without a database.
    """
    validation_errors: list[dict[str, Any]] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        data = proposal.get("data", {})
        errors = list(builder.validate(data))
        # Layer 2: chart-state validation (only the Rx parsers implement this).
        # Skip this step if we already failed on shape errors — the SDK call
        # is wasted work if the payload won't even build.
        if not errors and note_uuid:
            chart_validator = getattr(builder, "validate_against_patient", None)
            if callable(chart_validator):
                try:
                    chart_errors = chart_validator(data, note_uuid)
                except Exception:
                    # Fail open so transient DB issues don't block all writes,
                    # but log so schema drift / programming errors surface in
                    # the audit log instead of silently passing through.
                    log.exception(
                        "chart_validator raised in validate_proposals; failing open",
                    )
                    chart_errors = []
                errors.extend(chart_errors)
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
    proposals: list[dict[str, Any]], note_uuid: str
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
        meta = builder.pending_metadata(command, proposal)
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


def build_metadata_effects(pending: list[dict[str, Any]]) -> list[Effect]:
    """Phase 2: build upsert_metadata effects for commands that now exist in the DB."""
    effects: list[Effect] = []
    for item in pending:
        builder = _BUILDERS.get(item.get("command_type", ""))
        if builder is None:
            continue
        command = builder.build_stub(item["command_uuid"], item["note_uuid"])
        for key, value in item.get("metadata", {}).items():
            effects.append(command.upsert_metadata(key, value))
    return effects
