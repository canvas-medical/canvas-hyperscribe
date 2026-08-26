"""Shared helpers for toggling patient-chart command-button visibility (KOALA-5808).

Goal: while the provider is in the Scribe tab, hide every "+" command button in
the patient-chart sections (Conditions, Medications, Allergies, Vitals, ...) so
they document through the Scribe summary instead of the legacy chart rail. The
buttons return once they leave the Scribe tab.

OFF BY DEFAULT. The whole behavior sits behind the ``ScribeHideChartButtons``
secret (strict ``"true"``), because hiding the rail confused providers
(KOALA-5808 follow-up). Only the two HIDE paths below are gated. The three
RESTORE paths always run: they broadcast VISIBLE, which is the default state,
so they are idempotent when the feature is off and they clear any browser that
is still holding a hide from before the secret was switched off. That way the
flag has no setting in which a button vanishes with nothing left to bring it
back.

The one fact that shapes all of this: ``ConfigureCommandButtons`` is a **live
broadcast, not persisted state**, and it is scoped to the **patient**, not the
tab or the note. home-app's interpreter does nothing but push the hidden/disabled
location lists to the ``patient.<key>.command_button_visibility`` GraphQL
subscription; the only place the state lives is the ``hiddenLocations`` array in
each subscribed browser's ``CommandButtonVisibilityProvider``, mounted at the
patient-page level.

Two consequences that drive the design:

* It behaves as sticky *within a session*. The last broadcast wins and is never
  reset by a tab switch, a note collapse, or a sign — only by that provider
  remounting (full page reload, or navigating to a different patient). So every
  hide must be paired with a deliberate restore, or the buttons stay gone on the
  next, unrelated note.
* It is not per-user. The broadcast reaches every browser watching that patient,
  so a hide also blanks the chart rail for a colleague viewing the same patient
  concurrently. Not addressed here — tracked separately.

We therefore act at four moments:

1. Scribe tab opens -> HIDE. ``ScribeApp.handle()`` fires the hide effect when the
   tab opens (including default-open on note load, where no tab-change event is
   emitted). This is the initial hide.

2. Tab switches within the note -> HIDE or RESTORE. Canvas posts NOTE_TAB_CHANGE
   into the Scribe iframe on every switch; ``summary.js`` hits the
   ``/configure-command-buttons`` endpoint with hidden=true when the Scribe tab is
   active, hidden=false for any other tab.

3. Provider opens a different note on the same patient -> RESTORE.
   ``NoteCommandButtonsRestoreHandler`` listens for NOTE_CLOSED and restores
   unconditionally (restoring is harmless since buttons are visible by default).
   Note the narrow scope: home-app emits NOTE_CLOSED only as the
   ``previous_note_id`` side-channel of expanding another note, NOT when a note is
   simply collapsed.

4. Note is signed / otherwise leaves an editable state -> RESTORE.
   ``NoteSignedCommandButtonsRestoreHandler`` listens for
   NOTE_STATE_CHANGE_EVENT_CREATED. Signing auto-collapses the note, which
   destroys the Scribe iframe without a tab change AND without a NOTE_CLOSED, so
   neither (2) nor (3) fires — see that handler's docstring for the exact chain.

So HIDE has two triggers (tab open + switch-to-Scribe) and RESTORE has three
(switch-away, other-note-opened, left-editable-state), with the backend triggers
covering the cases the iframe can't. Centralizing effect construction here keeps
the hide and restore sides covering the same set of locations so they can't drift
apart.

KNOWN GAP: collapsing a note by hand (without signing it and without opening
another) still emits no event a plugin can see, so the buttons stay hidden until
the provider reloads or opens another note.

Do not "correct" this based on the SDK docs. The public NOTE_CLOSED docs say it
"fires when a provider collapses a note that was previously open," but as of
home-app develop that holds only when the collapse happens *by expanding another
note*: ``Notes.componentDidUpdate`` gates the call on ``if (expandedNoteId)`` so
a collapse to nothing never reaches ``onNoteExpanded``, ``NoteExpanded``'s
``currentNoteId`` is non-nullable, and the mutation emits NOTE_CLOSED only when
``previous_note_id is not None``. home-app's own test covers just the
previous_note_id-provided case. The fix belongs there, not here.

Requires a Canvas runtime >= 0.164.0 — the version that introduced both the
``ConfigureCommandButtons`` effect and the NOTE_CLOSED event. The feature cannot
function (and the plugin will not install) on older runtimes. Kept in sync with
``sdk_version`` in CANVAS_MANIFEST.json and the ``canvas`` pin in pyproject.toml;
all three must agree.
"""

from typing import Any

from canvas_sdk.effects import Effect
from canvas_sdk.effects.configure_command_buttons import ConfigureCommandButtons

from hyperscribe.libraries.constants import Constants


def command_button_hiding_enabled(secrets: dict[str, Any]) -> bool:
    """Return True when chart-section command-button hiding is switched on.

    Strict ``"true"`` match, like ``ScribeDictationEnabled``, so the secret can be
    set to ``false`` to disable rather than having to be deleted.
    """
    return str(secrets.get(Constants.SECRET_SCRIBE_HIDE_CHART_BUTTONS, "")).strip().lower() == "true"


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
