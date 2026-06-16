from __future__ import annotations

from canvas_sdk.effects import Effect
from canvas_sdk.effects.configure_command_buttons import ConfigureCommandButtons
from canvas_sdk.events import EventType
from canvas_sdk.handlers.base import BaseHandler

from hyperscribe.scribe.command_buttons import configure_command_buttons_effect


class NoteCommandButtonsRestoreHandler(BaseHandler):
    """Restore chart-section command buttons when a note is closed.

    The Scribe tab hides every command button while it is active (see
    ScribeApp.handle and the SimpleAPI toggle). That state is sticky and
    patient-scoped — Canvas keeps the buttons hidden on the chart until a plugin
    explicitly sets them visible again. The frontend restores them when the
    provider switches note tabs, but once the Scribe note is collapsed or the
    provider navigates to a different note, the Scribe iframe is gone and can no
    longer restore. Without this handler the buttons stay hidden even on an
    unrelated, non-Scribe note (KOALA-5808).

    NOTE_CLOSED fires when a provider collapses a note that was open. Its target
    is the patient, so we restore visibility for that patient unconditionally —
    the effect is idempotent (buttons are visible by default) and cheap, and a
    blanket restore is safer than trying to detect whether this particular note
    had ever triggered a hide.
    """

    RESPONDS_TO = [EventType.Name(EventType.NOTE_CLOSED)]

    def compute(self) -> list[Effect]:
        patient_id = self.event.target.id
        if not patient_id:
            return []
        return [
            configure_command_buttons_effect(
                patient_id,
                ConfigureCommandButtons.Visibility.VISIBLE,
            )
        ]
