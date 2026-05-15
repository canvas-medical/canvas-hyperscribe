from __future__ import annotations

import json
import uuid
from typing import Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.effects import Effect
from canvas_sdk.v1.data.note import Note
from pydantic import ValidationError

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
from hyperscribe.scribe.commands.image_results import ImageResultsParser
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
    "imaging_results": ImageResultsParser(),
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


def _build_unvalidated_metadata_effect(command: _BaseCommand, key: str, value: str) -> Effect:
    """Construct UPSERT_COMMAND_METADATA directly. The SDK helper
    validates Command.objects.filter(...).exists() at Python build time,
    which fails before originate has been applied. Canvas processes effects
    sequentially, so originate (STAGED) -> metadata (apply-time check passes)
    -> commit (COMMITTED with metadata attached) all in one response.

    Note: `Effect` is imported from `canvas_sdk.effects` (which re-exports the
    protobuf class) rather than the raw `canvas_generated.messages.effects_pb2`
    path, because the plugin-runner sandbox allowlists the former but not the
    latter."""
    return Effect(
        type="UPSERT_COMMAND_METADATA",
        payload=json.dumps(
            {
                "data": {
                    "schema_key": command.Meta.key,
                    "command_id": str(command.command_uuid),
                    "key": key,
                    "value": value,
                },
            }
        ),
    )


def _format_pydantic_errors(exc: ValidationError) -> list[str]:
    """Render pydantic errors as actionable one-liners for the provider UI."""
    messages: list[str] = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err.get("loc", ())) or "value"
        msg = err.get("msg", "Invalid value")
        messages.append(f"{loc}: {msg} (got {err['input']!r})")
    return messages


def build_effects(
    proposals: list[dict[str, Any]],
    note_uuid: str,
    feature_flags: dict[str, bool] | None = None,
) -> tuple[list[Effect], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Convert selected command proposals into Canvas SDK Effects.

    Each command is originated individually so a single failure doesn't
    take down unrelated commands. Effect order in the returned list is:

        originate_A, originate_B, ...,
        metadata_A, metadata_B, ...,    # only when pending_metadata is non-empty
        commit_A,   commit_B,   ...,

    Canvas processes effects sequentially, so by the time a metadata effect
    runs the corresponding originate effect has populated the Command row
    in the DB; by the time the commit effect runs, the metadata row is
    already attached to the (still STAGED) command.

    Returns (effects, metadata_pending, attempted, build_errors). When a
    proposal fails SDK construction (e.g. a vital outside its pydantic range),
    that single command is skipped and a structured error in the same shape as
    ``validate_proposals`` is appended to ``build_errors``; sibling commands
    still produce effects. ``metadata_pending`` is always empty now (metadata
    is emitted inline); kept in the signature so the legacy ``/insert-metadata``
    pathway continues to be a no-op without requiring a separate route change.
    """
    built: list[tuple[CommandParser, _BaseCommand, dict[str, Any]]] = []
    build_errors: list[dict[str, Any]] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        try:
            command = builder.build(proposal.get("data", {}), note_uuid, str(uuid.uuid4()))
        except ValidationError as exc:
            build_errors.append(
                {
                    "command_type": proposal.get("command_type", ""),
                    "display": (proposal.get("display") or "")[:80],
                    "errors": _format_pydantic_errors(exc),
                }
            )
            continue
        except ValueError as exc:
            build_errors.append(
                {
                    "command_type": proposal.get("command_type", ""),
                    "display": (proposal.get("display") or "")[:80],
                    "errors": [str(exc)],
                }
            )
            continue
        built.append((builder, command, proposal))

    if not built:
        return [], [], [], build_errors

    effects: list[Effect] = []
    for _, command, _ in built:
        effects.append(command.originate())

    for builder, command, proposal in built:
        meta = builder.pending_metadata(command, proposal, feature_flags)
        if not meta:
            continue
        for key, value in (meta.get("metadata") or {}).items():
            effects.append(_build_unvalidated_metadata_effect(command, key, value))

    for builder, command, proposal in built:
        effects.extend(builder.post_originate_effects(command, proposal))

    attempted = [
        {
            "command_uuid": str(command.command_uuid),
            "command_type": builder.command_type,
            "display": (proposal.get("display") or "")[:80],
        }
        for builder, command, proposal in built
    ]

    return effects, [], attempted, build_errors


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
