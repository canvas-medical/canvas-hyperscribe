from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from canvas_sdk.commands.base import _BaseCommand
from canvas_sdk.effects import Effect

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

    def validate(self, data: dict[str, Any]) -> list[str]:
        """Return validation error strings, or empty list if valid. Override per command type."""
        return []

    @abstractmethod
    def build(self, data: dict[str, Any], note_uuid: str, command_uuid: str) -> _BaseCommand: ...

    def to_effects(self, command: _BaseCommand, note_uuid: str | None = None) -> list[Effect]:
        """Convert a built command into Canvas SDK Effects.

        Default: originate + commit. Override for commands that need
        a different effect sequence (e.g. questionnaires: originate + edit).
        """
        effects = [command.originate()]
        try:
            effects.append(command.commit())
        except Exception as exc:
            if note_uuid:
                from hyperscribe.scribe.api.session_view import audit_event

                audit_event(
                    note_uuid,
                    "COMMIT_FAILED",
                    {
                        "command_type": self.command_type,
                        "command_uuid": command.command_uuid,
                        "error": str(exc),
                    },
                )
        return effects

    def post_originate_effects(self, command: _BaseCommand, proposal: dict[str, Any] | None = None) -> list[Effect]:
        """Effects to apply AFTER origination (commit, review, etc)."""
        try:
            return [command.commit()]
        except Exception:
            return []

    def pending_metadata(
        self,
        command: _BaseCommand,
        proposal: dict[str, Any] | None = None,
        feature_flags: dict[str, bool] | None = None,
    ) -> dict[str, Any] | None:
        """Return metadata to upsert in phase 2, or None. Override per command type."""
        return None

    def build_stub(self, command_uuid: str, note_uuid: str) -> _BaseCommand:
        """Build a minimal command for phase 2 metadata operations."""
        raise NotImplementedError
