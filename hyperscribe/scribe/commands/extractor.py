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


def _parse_ros_subsections(text: str) -> list[dict[str, str]]:
    """Parse ROS text into subsections by system header (e.g. 'General:', 'Skin:')."""
    sections: list[dict[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    for raw_line in text.split("\n"):
        line = raw_line.strip()
        if not line:
            continue
        # Strip leading bullet markers.
        cleaned = line.lstrip("-*\u2022").strip()
        # Check if this line is a system header like "General: ..."
        if ":" in cleaned:
            label, _, rest = cleaned.partition(":")
            # A system header has a short label (1-3 words, no bullets in the rest as first char).
            words = label.split()
            if 1 <= len(words) <= 3 and label[0].isupper():
                # Flush previous section.
                if current_title:
                    sections.append(
                        {
                            "key": current_title.lower().replace(" ", "_"),
                            "title": current_title,
                            "text": "\n".join(current_lines).strip(),
                        }
                    )
                current_title = label.strip()
                current_lines = [rest.strip()] if rest.strip() else []
                continue
        current_lines.append(line)

    if current_title:
        sections.append(
            {
                "key": current_title.lower().replace(" ", "_"),
                "title": current_title,
                "text": "\n".join(current_lines).strip(),
            }
        )
    return sections


def _extract_ros(note: ClinicalNote) -> CommandProposal | None:
    """Extract review_of_systems section into an ROS command with per-system subsections."""
    ros_section = next(
        (s for s in note.sections if s.key.lower() == "review_of_systems" and s.text.strip()),
        None,
    )
    if ros_section is None:
        return None
    subsections = _parse_ros_subsections(ros_section.text)
    if not subsections:
        # Fall back to a single section if no system headers were detected.
        subsections = [{"key": "review_of_systems", "title": "Review of Systems", "text": ros_section.text.strip()}]
    display = " | ".join(s["title"] for s in subsections)
    return CommandProposal(
        command_type="ros",
        display=display,
        data={"sections": subsections},
        section_key="_ros",
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

    ros_proposal = _extract_ros(note)
    if ros_proposal is not None:
        proposals.append(ros_proposal)

    history_proposal = _extract_history_review(note)
    if history_proposal is not None:
        proposals.append(history_proposal)

    chart_proposal = _extract_chart_review(note)
    if chart_proposal is not None:
        proposals.append(chart_proposal)

    return proposals
