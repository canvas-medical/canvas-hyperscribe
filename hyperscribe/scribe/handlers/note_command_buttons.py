from __future__ import annotations

from canvas_sdk.effects import Effect
from canvas_sdk.effects.configure_command_buttons import ConfigureCommandButtons
from canvas_sdk.events import EventType
from canvas_sdk.handlers.base import BaseHandler
from canvas_sdk.v1.data.note import NoteStateChangeEvent

from hyperscribe.scribe.command_buttons import command_button_hiding_enabled, configure_command_buttons_effect
from hyperscribe.scribe.handlers.note_state import _EDITABLE_STATES


class NoteCommandButtonsRestoreHandler(BaseHandler):
    """Restore chart-section command buttons when the provider opens another note.

    The Scribe tab hides every command button while it is active (see
    ScribeApp.handle and the SimpleAPI toggle). That hide is a per-patient
    broadcast with no server-side state, so it persists in every subscribed
    browser until something broadcasts VISIBLE again — see command_buttons.py for
    the full model. The frontend restores on a note-tab switch, but once the
    provider moves to a different note the Scribe iframe is gone and can no longer
    restore. Without this handler the buttons stay hidden even on an unrelated,
    non-Scribe note (KOALA-5808).

    Its target is the patient, so we restore visibility for that patient without
    checking whether this particular note ever triggered a hide — the effect is
    idempotent (buttons are visible by default) and cheap, and a blanket restore
    is safer than trying to reconstruct that history.

    Gated on ScribeHideChartButtons like every other path in the feature, so
    with the secret off this handler emits nothing. See command_buttons.py for
    why the restores are gated rather than left always-on.

    SCOPE — NOTE_CLOSED is narrower than its name suggests. home-app only emits
    it as the ``previous_note_id`` side-channel of *expanding a different note*
    (``NoteExpandedMutation``); ``Notes.componentDidUpdate`` skips the callback
    entirely when the newly-expanded id is null. So a note that is merely
    collapsed — including the auto-collapse that fires when a note is signed —
    produces no NOTE_CLOSED. NoteSignedCommandButtonsRestoreHandler below covers
    the signed path off the state-change event instead.
    """

    RESPONDS_TO = [EventType.Name(EventType.NOTE_CLOSED)]

    def compute(self) -> list[Effect]:
        if not command_button_hiding_enabled(self.secrets):
            return []
        patient_id = self.event.target.id
        if not patient_id:
            return []
        return [
            configure_command_buttons_effect(
                patient_id,
                ConfigureCommandButtons.Visibility.VISIBLE,
            )
        ]


class NoteSignedCommandButtonsRestoreHandler(BaseHandler):
    """Restore chart-section command buttons when a note leaves an editable state.

    Signing a note is the one exit from the Scribe tab that neither of the
    original restore paths caught (KOALA-5808 follow-up):

    * No NOTE_TAB_CHANGE — home-app auto-collapses the note the moment it becomes
      locked (``Note.shouldAutoCollapse``), so the Scribe iframe is destroyed
      without any tab ever becoming active. The frontend restore never runs.
    * No NOTE_CLOSED — the auto-collapse sets ``expandedNoteId`` to null, and
      ``Notes.componentDidUpdate`` only calls ``onNoteExpanded`` when a note *is*
      expanded, so the mutation that emits NOTE_CLOSED is never called.

    The result was buttons stuck hidden on the patient's chart after a sign, for
    every browser subscribed to that patient's command-button channel, until a
    full page reload. NOTE_STATE_CHANGE_EVENT_CREATED is the reliable signal:
    it's the same event NoteLockGuard gates on at PRE_CREATE, so a lock cannot
    happen without it.

    Deliberately NOT gated on the note having a ScribeTranscript/ScribeSummary
    row (the check NoteStateHandler makes). ``ScribeApp.handle()`` hides the
    buttons whenever the Scribe tab opens, which includes default-open on note
    load — so a provider can open a note, chart nothing in Scribe, and sign,
    leaving no Scribe row behind. That is precisely the case a has-Scribe gate
    would skip and the one that leaves the buttons stranded.

    Restores only on transitions *out* of an editable state. Transitions back in
    (unlock for an amend) need no restore: reopening the note reopens the Scribe
    tab, which re-asserts the hide.

    Gated on ScribeHideChartButtons, checked before the query so a disabled
    feature costs nothing on an event that fires for every note state change.
    """

    RESPONDS_TO = [EventType.Name(EventType.NOTE_STATE_CHANGE_EVENT_CREATED)]

    def compute(self) -> list[Effect]:
        if not command_button_hiding_enabled(self.secrets):
            return []
        try:
            state_event = NoteStateChangeEvent.objects.values("state", "note__patient__id").get(id=self.event.target.id)
        except NoteStateChangeEvent.DoesNotExist:
            return []
        if state_event["state"] in _EDITABLE_STATES:
            return []
        patient_id = state_event["note__patient__id"]
        if not patient_id:
            return []
        return [
            configure_command_buttons_effect(
                patient_id,
                ConfigureCommandButtons.Visibility.VISIBLE,
            )
        ]
