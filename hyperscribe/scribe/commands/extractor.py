from __future__ import annotations

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal
from hyperscribe.scribe.commands.base import CommandParser
from hyperscribe.scribe.commands.hpi import HpiParser
from hyperscribe.scribe.commands.medication_statement import MedicationParser
from hyperscribe.scribe.commands.plan import PlanParser
from hyperscribe.scribe.commands.rfv import RfvParser
from hyperscribe.scribe.commands.vitals import VitalsParser

_SECTION_PARSERS: dict[str, CommandParser] = {
    "chief_complaint": RfvParser(),
    "history_of_present_illness": HpiParser(),
    "plan": PlanParser(),
    "vitals": VitalsParser(),
    "current_medications": MedicationParser(),
}


def extract_commands(note: ClinicalNote) -> list[CommandProposal]:
    """Map ClinicalNote sections to CommandProposal list (deterministic, no LLM)."""
    proposals: list[CommandProposal] = []
    for section in note.sections:
        parser = _SECTION_PARSERS.get(section.key.lower())
        if parser is None:
            continue
        text = section.text.strip()
        if not text:
            continue
        for proposal in parser.extract_all(text):
            proposal.section_key = section.key.lower()
            proposals.append(proposal)
    return proposals
