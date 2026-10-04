from __future__ import annotations

from canvas_sdk.effects import Effect
from canvas_sdk.effects.validation import EventValidationError, ValidationError
from canvas_sdk.events import EventType
from canvas_sdk.handlers.base import BaseHandler
from canvas_sdk.v1.data.note import Note

from hyperscribe.libraries.constants import Constants
from hyperscribe.models.scribe import ScribeSummary, ScribeTranscript

# Mirrors session_view.FROM_THE_NOTE_SECTION / scribe_data.FROM_THE_NOTE_SECTION.
# Commands carrying this section_key are reflections of commands the provider
# added directly to the note body (the "Additional Commands" rail), not Scribe
# work product, so they do not count as Scribe usage for the lock gate.
_FROM_THE_NOTE_SECTION = "from_the_note"


def _scribe_pending_finalization(note_dbid: int) -> bool:
    """Return True when Scribe was meaningfully used on this note but is not finalized.

    "Finalized" is ``ScribeSummary.approved`` (the frontend's own definition:
    ``amending = wasFinalized && !approved``). The flag is persisted to the DB in
    real time via ``/save-summary``, so reading it here reflects both first-time
    generation (never approved) and amendment-in-progress (approved reset to False).

    Synced note-body commands (``section_key == "from_the_note"``) do NOT count as
    Scribe usage.
    """
    summary = ScribeSummary.objects.filter(note_id=note_dbid).values("commands", "note_data", "approved").first()
    if summary and summary["approved"]:
        return False  # finalized -> allow lock

    # A recording transcript is meaningful Scribe usage.
    if ScribeTranscript.objects.filter(note_id=note_dbid).values_list("items", flat=True).first():
        return True

    if not summary:
        return False  # no Scribe content at all -> gate ignored

    real_commands = [
        command
        for command in (summary["commands"] or [])
        if (command or {}).get("section_key") != _FROM_THE_NOTE_SECTION
    ]
    if real_commands:
        return True

    sections = (summary.get("note_data") or {}).get("sections") or []
    return any((section.get("text") or "").strip() for section in sections)


class NoteLockGuard(BaseHandler):
    """Blocks locking a note documented with Scribe until the Scribe tab is finalized."""

    RESPONDS_TO = [EventType.Name(EventType.NOTE_STATE_CHANGE_EVENT_PRE_CREATE)]

    def compute(self) -> list[Effect]:
        # Only gate the Lock/Sign transition; pushing charges (PSH) is not gated.
        if self.event.context.get("state") != "LKD":
            return []

        note_uuid = self.event.context.get("note_id")
        note_dbid = Note.objects.filter(id=note_uuid).values_list("dbid", flat=True).first()
        if not note_dbid:
            return []

        if not _scribe_pending_finalization(note_dbid):
            return []

        tab_name = self.secrets.get(Constants.SECRET_SCRIBE_TAB_NAME) or "Scribe"
        return [
            EventValidationError(
                errors=[
                    ValidationError(
                        message=(
                            f"This note can't be signed until the {tab_name} tab is finalized. "
                            f"Open {tab_name}, review the summary, and click Approve."
                        )
                    )
                ]
            ).apply()
        ]
