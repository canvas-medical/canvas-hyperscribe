from __future__ import annotations

from typing import Any

from canvas_sdk.effects import Effect

from hyperscribe.scribe.commands.base import CommandParser
from hyperscribe.scribe.commands.hpi import HpiParser
from hyperscribe.scribe.commands.medication_statement import MedicationParser
from hyperscribe.scribe.commands.plan import PlanParser
from hyperscribe.scribe.commands.rfv import RfvParser
from hyperscribe.scribe.commands.vitals import VitalsParser

_BUILDERS: dict[str, CommandParser] = {
    "hpi": HpiParser(),
    "medication_statement": MedicationParser(),
    "plan": PlanParser(),
    "rfv": RfvParser(),
    "vitals": VitalsParser(),
}


def build_effects(proposals: list[dict[str, Any]], note_uuid: str) -> list[Effect]:
    """Convert selected command proposals into Canvas SDK Effects."""
    effects: list[Effect] = []
    for proposal in proposals:
        builder = _BUILDERS.get(proposal.get("command_type", ""))
        if builder is None:
            continue
        command = builder.build(proposal.get("data", {}), note_uuid)
        effects.append(command.originate())
    return effects
