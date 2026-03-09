from __future__ import annotations

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal

_MAX_DISPLAY_LEN = 80

_SECTION_TO_COMMAND: dict[str, str] = {
    "chief_complaint": "rfv",
    "history_of_present_illness": "hpi",
    "plan": "plan",
}

_COMMAND_DATA_FIELD: dict[str, str] = {
    "rfv": "comment",
    "hpi": "narrative",
    "plan": "narrative",
}


def _truncate(text: str, max_len: int = _MAX_DISPLAY_LEN) -> str:
    if len(text) <= max_len:
        return text
    return text[: max_len - 3].rstrip() + "..."


def extract_commands(note: ClinicalNote) -> list[CommandProposal]:
    """Map ClinicalNote sections to CommandProposal list (deterministic, no LLM)."""
    proposals: list[CommandProposal] = []
    for section in note.sections:
        key = section.key.lower()
        text = section.text.strip()
        if not text:
            continue
        cmd_type = _SECTION_TO_COMMAND.get(key)
        if cmd_type is None:
            continue
        field = _COMMAND_DATA_FIELD[cmd_type]
        proposals.append(
            CommandProposal(
                command_type=cmd_type,
                display=_truncate(text),
                data={field: text},
            )
        )
    return proposals
