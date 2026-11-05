from __future__ import annotations

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Broadcast
from canvas_sdk.events import EventType
from canvas_sdk.handlers.base import BaseHandler
from canvas_sdk.v1.data.note import NoteStateChangeEvent, NoteStates

from hyperscribe.models.scribe import ScribeSummary, ScribeTranscript


_EDITABLE_STATES = frozenset(
    {
        NoteStates.NEW,
        NoteStates.PUSHED,
        NoteStates.UNLOCKED,
        NoteStates.RESTORED,
        NoteStates.UNDELETED,
        NoteStates.CONVERTED,
    }
)


class NoteStateHandler(BaseHandler):
    """Broadcasts note state changes to Scribe WebSocket clients."""

    RESPONDS_TO = [EventType.Name(EventType.NOTE_STATE_CHANGE_EVENT_CREATED)]

    def compute(self) -> list[Effect]:
        state_event_id = self.event.target.id
        try:
            state_event = NoteStateChangeEvent.objects.select_related("note").get(id=state_event_id)
        except NoteStateChangeEvent.DoesNotExist:
            return []

        note_dbid = state_event.note.dbid

        # Only broadcast for notes that have an active Scribe session.
        has_scribe = (
            ScribeTranscript.objects.filter(note_id=note_dbid).exists()
            or ScribeSummary.objects.filter(note_id=note_dbid).exists()
        )
        if not has_scribe:
            return []

        note_uuid = str(state_event.note.id)
        editable = state_event.state in _EDITABLE_STATES

        return [
            Broadcast(
                channel=f"scribe-{note_uuid}",
                message={
                    "type": "NOTE_STATE_CHANGED",
                    "note_id": note_uuid,
                    "state": state_event.state,
                    "editable": editable,
                },
            ).apply()
        ]
