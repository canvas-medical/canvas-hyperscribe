from __future__ import annotations

import uuid
from typing import Any

from canvas_sdk.effects import Effect
from canvas_sdk.v1.data.note import Note

from hyperscribe.scribe.backend.models import CommandProposal
from hyperscribe.scribe.commands.allergy import AllergyParser
from hyperscribe.scribe.commands.assess import AssessParser
from hyperscribe.scribe.commands.base import CommandParser
from hyperscribe.scribe.commands.chart_review import ChartReviewParser
from hyperscribe.scribe.commands.diagnose import DiagnoseParser
from hyperscribe.scribe.commands.history_review import HistoryReviewParser
from hyperscribe.scribe.commands.hpi import HpiParser
from hyperscribe.scribe.commands.imaging_order import ImagingOrderParser
from hyperscribe.scribe.commands.lab_order import LabOrderParser
from hyperscribe.scribe.commands.medication_statement import MedicationParser
from hyperscribe.scribe.commands.plan import PlanParser
from hyperscribe.scribe.commands.prescription import PrescriptionParser
from hyperscribe.scribe.commands.rfv import RfvParser
from hyperscribe.scribe.commands.ros import RosParser
from hyperscribe.scribe.commands.task import TaskParser
from hyperscribe.scribe.commands.vitals import VitalsParser

_BUILDERS: dict[str, CommandParser] = {
    "allergy": AllergyParser(),
    "assess": AssessParser(),
    "chart_review": ChartReviewParser(),
    "diagnose": DiagnoseParser(),
    "history_review": HistoryReviewParser(),
    "hpi": HpiParser(),
    "imaging_order": ImagingOrderParser(),
    "lab_order": LabOrderParser(),
    "medication_statement": MedicationParser(),
    "plan": PlanParser(),
    "prescribe": PrescriptionParser(),
    "rfv": RfvParser(),
    "ros": RosParser(),
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


def build_effects(proposals: list[dict[str, Any]], note_uuid: str) -> list[Effect]:
    """Convert selected command proposals into Canvas SDK Effects."""
    effects: list[Effect] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        command = builder.build(proposal.get("data", {}), note_uuid, str(uuid.uuid4()))
        effects.append(command.originate())
        try:
            # some commands cannot be commited, i.e. CustomCommands.
            effects.append(command.commit())
        except Exception:
            pass
    return effects
