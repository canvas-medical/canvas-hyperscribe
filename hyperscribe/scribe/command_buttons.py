"""Shared helpers for toggling patient-chart command-button visibility (KOALA-5808).

Goal: while the provider is in the Scribe tab, hide every "+" command button in
the patient-chart sections (Conditions, Medications, Allergies, Vitals, ...) so
they document through the Scribe summary instead of the legacy chart rail. The
buttons return once they leave the Scribe tab.

The one fact that shapes all of this: ``ConfigureCommandButtons`` is *sticky* and
scoped to the **patient**, not the tab. Telling Canvas "hide" keeps the buttons
hidden on that patient's chart until we explicitly say "show" again — it does NOT
reset on tab switch or when the note closes. So every hide must be paired with a
deliberate restore, or the buttons stay gone even on an unrelated note.

We therefore act at three moments:

1. Scribe tab opens -> HIDE. ``ScribeApp.handle()`` fires the hide effect when the
   tab opens (including default-open on note load, where no tab-change event is
   emitted). This is the initial hide.

2. Tab switches within the note -> HIDE or RESTORE. Canvas posts NOTE_TAB_CHANGE
   into the Scribe iframe on every switch; ``summary.js`` hits the
   ``/configure-command-buttons`` endpoint with hidden=true when the Scribe tab is
   active, hidden=false for any other tab.

3. Note closes / provider leaves -> RESTORE (the safety net). When the provider
   closes the note or jumps to a different one, the Scribe iframe is destroyed and
   can no longer send a restore. ``NoteCommandButtonsRestoreHandler`` listens for
   the NOTE_CLOSED event and restores buttons for the patient unconditionally
   (restoring is harmless since buttons are visible by default). Without this the
   buttons would stay hidden on the next, unrelated note.

So HIDE has two triggers (tab open + switch-to-Scribe) and RESTORE has two
(switch-away + note close), with the backend triggers covering the cases the
iframe can't. Centralizing effect construction here keeps the hide and restore
sides covering the same set of locations so they can't drift apart.

Requires a Canvas runtime >= 0.163.0 — the version that introduced both the
``ConfigureCommandButtons`` effect and the NOTE_CLOSED event. The feature cannot
function (and the plugin will not install) on older runtimes.
"""

from canvas_sdk.effects import Effect
from canvas_sdk.effects.configure_command_buttons import ConfigureCommandButtons


def configure_command_buttons_effect(
    patient_id: str,
    visibility: ConfigureCommandButtons.Visibility,
) -> Effect:
    """Build an effect setting every command-button location to ``visibility``.

    Iterates the full Location enum rather than naming a subset so locations
    Canvas adds later are covered automatically.
    """
    return ConfigureCommandButtons(
        patient_id=str(patient_id),
        locations=[
            ConfigureCommandButtons.LocationConfig(location=location, visibility=visibility)
            for location in ConfigureCommandButtons.Location
        ],
    ).apply()
