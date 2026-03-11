from __future__ import annotations

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal
from hyperscribe.scribe.commands.base import CommandParser
from hyperscribe.scribe.commands.hpi import HpiParser
from hyperscribe.scribe.commands.plan import PlanParser
from hyperscribe.scribe.commands.rfv import RfvParser
from hyperscribe.scribe.commands.vitals import VitalsParser

_SECTION_PARSERS: dict[str, CommandParser] = {
    "chief_complaint": RfvParser(),
    "history_of_present_illness": HpiParser(),
    "plan": PlanParser(),
    "assessment_and_plan": PlanParser(),
    "vitals": VitalsParser(),
}

_CHART_REVIEW_KEYS: frozenset[str] = frozenset(
    {
        "current_medications",
        "allergies",
        "immunizations",
    }
)

_HISTORY_REVIEW_KEYS: frozenset[str] = frozenset(
    {
        "past_medical_history",
        "past_surgical_history",
        "past_obstetric_history",
        "family_history",
        "social_history",
    }
)


def _extract_history_review(note: ClinicalNote) -> CommandProposal | None:
    """Combine history sections into one History Review command."""
    sections = [
        {"key": s.key.lower(), "title": s.title, "text": s.text.strip()}
        for s in note.sections
        if s.key.lower() in _HISTORY_REVIEW_KEYS and s.text.strip()
    ]
    if not sections:
        return None
    display = " | ".join(s["title"] for s in sections)
    return CommandProposal(
        command_type="history_review",
        display=display,
        data={"sections": sections},
        section_key="_history_review",
    )


def _extract_chart_review(note: ClinicalNote) -> CommandProposal | None:
    """Combine chart review sections into one Chart Review command."""
    sections = [
        {"key": s.key.lower(), "title": s.title, "text": s.text.strip()}
        for s in note.sections
        if s.key.lower() in _CHART_REVIEW_KEYS and s.text.strip()
    ]
    if not sections:
        return None
    display = " | ".join(s["title"] for s in sections)
    return CommandProposal(
        command_type="chart_review",
        display=display,
        data={"sections": sections},
        section_key="_chart_review",
    )


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

    history_proposal = _extract_history_review(note)
    if history_proposal is not None:
        proposals.append(history_proposal)

    chart_proposal = _extract_chart_review(note)
    if chart_proposal is not None:
        proposals.append(chart_proposal)

    return proposals
