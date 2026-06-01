from __future__ import annotations

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, Observation
from hyperscribe.scribe.commands.base import CommandParser
from hyperscribe.scribe.commands.hpi import HpiParser
from hyperscribe.scribe.commands.plan import PlanParser
from hyperscribe.scribe.commands.rfv import RfvParser
from hyperscribe.scribe.commands.vitals import VitalsExtractionResult, VitalsParser

_VITALS_PARSER = VitalsParser()

_SECTION_PARSERS: dict[str, CommandParser] = {
    "chief_complaint": RfvParser(),
    "history_of_present_illness": HpiParser(),
    "plan": PlanParser(),
    "assessment_and_plan": PlanParser(),
    "appointments": PlanParser(),
    "vitals": _VITALS_PARSER,
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


def parse_ros_subsections(text: str) -> list[dict[str, str]]:
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
    subsections = parse_ros_subsections(ros_section.text)
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


def _extract_physical_exam(note: ClinicalNote) -> CommandProposal | None:
    """Extract physical_exam section into a PE command with per-system subsections."""
    pe_section = next(
        (s for s in note.sections if s.key.lower() == "physical_exam" and s.text.strip()),
        None,
    )
    if pe_section is None:
        return None
    subsections = parse_ros_subsections(pe_section.text)
    if not subsections:
        # Fall back to a single section if no system headers were detected.
        subsections = [{"key": "physical_exam", "title": "Physical Exam", "text": pe_section.text.strip()}]
    display = " | ".join(s["title"] for s in subsections)
    return CommandProposal(
        command_type="physical_exam",
        display=display,
        data={"sections": subsections},
        section_key="physical_exam",
    )


_CHART_REVIEW_TITLE_OVERRIDES: dict[str, str] = {
    "current_medications": "Meds Discussed",
    "allergies": "Allergies Discussed",
}


def _extract_chart_review(note: ClinicalNote) -> CommandProposal | None:
    """Combine chart review sections into one Chart Review command."""
    sections = [
        {
            "key": s.key.lower(),
            "title": _CHART_REVIEW_TITLE_OVERRIDES.get(s.key.lower(), s.title),
            "text": s.text.strip(),
        }
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


def _extract_lab_results(note: ClinicalNote) -> CommandProposal | None:
    """Extract lab_results section into a Lab Review command."""
    lab_section = next(
        (s for s in note.sections if s.key.lower() == "lab_results" and s.text.strip()),
        None,
    )
    if lab_section is None:
        return None
    text = lab_section.text.strip()
    return CommandProposal(
        command_type="lab_results",
        display=text,
        data={"narrative": text},
        section_key="lab_results",
    )


def _extract_image_results(note: ClinicalNote) -> CommandProposal | None:
    """Extract imaging_results section into an Image Results command."""
    image_section = next(
        (s for s in note.sections if s.key.lower() == "imaging_results" and s.text.strip()),
        None,
    )
    if image_section is None:
        return None
    text = image_section.text.strip()
    return CommandProposal(
        command_type="imaging_results",
        display=text,
        data={"narrative": text},
        section_key="imaging_results",
    )


def _extract_vitals(note: ClinicalNote, observations: list[Observation]) -> CommandProposal | None:
    """Extract vitals from the note's vitals section plus Nabla's structured observations.

    Observations are preferred (LOINC-coded, unit-aware); the free-text regex on the
    vitals section is used as a fallback for fields the observations didn't cover.
    Emits a proposal when *either* source yields data — covers the case where Nabla
    populated observations but emitted no vitals section text, and vice versa.
    """
    result = extract_vitals_with_telemetry(note, observations)
    return result.proposal


def extract_vitals_with_telemetry(
    note: ClinicalNote,
    observations: list[Observation],
) -> VitalsExtractionResult:
    """Run the vitals extraction and return the proposal plus audit metadata.

    Wraps ``VitalsParser.extract_with_telemetry`` and tags the proposal with
    ``section_key="vitals"`` so callers can use the proposal directly.
    Returns the canonical ``source`` label derived from the FINAL surviving
    fields (not raw inputs) — this is the chokepoint
    ``post_generate_summary`` uses to emit ``VITALS_SOURCE`` and
    ``VITALS_FIELD_REFUSED`` from a single extraction pass.
    """
    vitals_section = next(
        (s for s in note.sections if s.key.lower() == "vitals"),
        None,
    )
    text = vitals_section.text.strip() if vitals_section is not None else ""
    if not text and not observations:
        return VitalsExtractionResult(proposal=None, refusals=[], source="none")
    result = _VITALS_PARSER.extract_with_telemetry(text, observations)
    if result.proposal is not None:
        result.proposal.section_key = "vitals"
    return result


def classify_vitals_source(note: ClinicalNote, observations: list[Observation]) -> str:
    """Return which parser populated the vitals proposal: ``observations``, ``regex``, ``both``, or ``none``.

    Purely diagnostic. Used by the API layer to emit a ``VITALS_SOURCE`` audit
    event so we can measure observation-vs-regex reliability in prod and
    eventually retire the loser parser.

    Classifies from the FINAL surviving fields of the proposal (not raw
    inputs) so a fully-refused observation panel doesn't get counted as
    ``observations`` in telemetry. Risk-hunter flagged the race:
    pre-validation classification overstated the observation path's
    reliability when Nabla emitted out-of-range BP and the per-field gate
    plus atomic-pair sweep dropped both sides.
    """
    return extract_vitals_with_telemetry(note, observations).source


def extract_commands(
    note: ClinicalNote,
    observations: list[Observation] | None = None,
) -> list[CommandProposal]:
    """Map ClinicalNote sections to CommandProposal list (deterministic, no LLM).

    ``observations`` carries Nabla's normalized vital signs (LOINC-coded). Pass them
    when available so the vitals parser can avoid format-drift bugs that plague the
    regex over Nabla's free-text vitals string.
    """
    obs = observations or []
    proposals: list[CommandProposal] = []
    # Track the insertion point for the vitals proposal so it lands in section order
    # even though we route vitals through the observation-aware path below. We capture
    # the position as we encounter the vitals section rather than recomputing it after
    # the loop — this stays correct regardless of how many proposals each upstream
    # parser emits per section (e.g. medication_statement / allergy override
    # extract_all to emit multiple).
    vitals_position: int | None = None
    for section in note.sections:
        if section.key.lower() == "vitals":
            if vitals_position is None:
                vitals_position = len(proposals)
            continue
        parser = _SECTION_PARSERS.get(section.key.lower())
        if parser is None:
            continue
        text = section.text.strip()
        if not text:
            continue
        for proposal in parser.extract_all(text):
            proposal.section_key = section.key.lower()
            proposals.append(proposal)

    vitals_proposal = _extract_vitals(note, obs)
    if vitals_proposal is not None:
        if vitals_position is None:
            proposals.append(vitals_proposal)
        else:
            proposals.insert(vitals_position, vitals_proposal)

    ros_proposal = _extract_ros(note)
    if ros_proposal is not None:
        proposals.append(ros_proposal)

    pe_proposal = _extract_physical_exam(note)
    if pe_proposal is not None:
        proposals.append(pe_proposal)

    history_proposal = _extract_history_review(note)
    if history_proposal is not None:
        proposals.append(history_proposal)

    chart_proposal = _extract_chart_review(note)
    if chart_proposal is not None:
        proposals.append(chart_proposal)

    lab_proposal = _extract_lab_results(note)
    if lab_proposal is not None:
        proposals.append(lab_proposal)

    image_proposal = _extract_image_results(note)
    if image_proposal is not None:
        proposals.append(image_proposal)

    return proposals
