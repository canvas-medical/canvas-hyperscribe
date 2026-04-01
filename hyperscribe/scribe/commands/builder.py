from __future__ import annotations

import uuid
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.effects import Effect
from canvas_sdk.effects.batch_originate import BatchOriginateCommandEffect
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


def build_effects(proposals: list[dict[str, Any]], note_uuid: str) -> tuple[list[Effect], list[dict[str, Any]]]:
    """Convert selected command proposals into Canvas SDK Effects.

    Returns (effects, metadata_pending) where metadata_pending contains items
    that need a second request to upsert metadata after commands exist.
    """
    built: list[tuple[CommandParser, _BaseCommand, dict[str, Any]]] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        command = builder.build(proposal.get("data", {}), note_uuid, str(uuid.uuid4()))
        built.append((builder, command, proposal))

    if not built:
        return [], []

    # CustomCommand types must originate individually — batch originate doesn't handle schema_key correctly.
    _INDIVIDUAL_ORIGINATE = frozenset({"chart_review", "history_review", "ros", "physical_exam"})
    batch_commands = [(b, cmd, p) for b, cmd, p in built if b.command_type not in _INDIVIDUAL_ORIGINATE]
    individual_commands = [(b, cmd, p) for b, cmd, p in built if b.command_type in _INDIVIDUAL_ORIGINATE]

    effects: list[Effect] = []
    if batch_commands:
        batch = BatchOriginateCommandEffect(commands=[cmd for _, cmd, _ in batch_commands])
        effects.append(batch.apply())
    for _, command, _ in individual_commands:
        effects.append(command.originate())

    # Post-origination effects (commit/review/edit) per command.
    metadata_pending: list[dict[str, Any]] = []
    for builder, command, proposal in built:
        effects.extend(builder.post_originate_effects(command, proposal))
        meta = builder.pending_metadata(command, proposal)
        if meta:
            metadata_pending.append(meta)

    return effects, metadata_pending


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
