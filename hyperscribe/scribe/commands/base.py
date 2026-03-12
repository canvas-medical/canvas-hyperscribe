from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from canvas_sdk.commands.base import _BaseCommand

from hyperscribe.scribe.backend.models import CommandProposal

if TYPE_CHECKING:
    from canvas_sdk.v1.data.note import Note


class CommandParser(ABC):
    """Base class for section-to-command parsers.

    Subclasses must set ``command_type`` and implement ``build``.
    Text-based commands should also set ``data_field``; the default
    ``extract`` will wrap the section text in that field.  Structured
    commands (e.g. vitals) should leave ``data_field`` as ``None`` and
    override ``extract``.
    """

    command_type: str
    data_field: str | None = None

    def extract(self, text: str) -> CommandProposal | None:
        if self.data_field is None:
            raise NotImplementedError(f"{type(self).__name__} must override extract()")
        return CommandProposal(
            command_type=self.command_type,
            display=text,
            data={self.data_field: text},
        )

    def extract_all(self, text: str) -> list[CommandProposal]:
        proposal = self.extract(text)
        return [proposal] if proposal is not None else []

    def annotate_duplicates(self, proposals: list[CommandProposal], note: Note) -> None:
        """Mark proposals that already exist in the patient's chart. Override per command type."""

    @abstractmethod
    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand: ...
