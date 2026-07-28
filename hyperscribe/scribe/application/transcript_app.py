from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import NoteApplication
from canvas_sdk.v1.data.note import Note

from canvas_sdk.events import Event
from canvas_sdk.v1.data.staff import Staff

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.models.scribe import ScribeSummary, ScribeTranscript
from hyperscribe.structures.settings import Settings

_CACHE_KEY_PREFIX = "scribe_transcript:"


def _staff_key_from_actor(event: Event) -> str:
    """Resolve the event actor (CanvasUser dbid) to the Staff key used by plugins."""
    actor_id = event.actor.id
    if not actor_id:
        return ""
    key = Staff.objects.filter(user__dbid=actor_id).values_list("id", flat=True).first()
    return str(key or "")


def is_scribe_visible(secrets: dict[str, str], event: Event) -> bool:
    """Return True when scribe should be visible for this staff/note combination.

    Checks scribe modality and, when configured, allowed note types.
    """
    # PILOT: revert to `secrets.get(Constants.SECRET_MODALITY, "").lower() == Constants.MODALITY_SCRIBE`
    settings = Settings.from_dictionary(secrets)
    staff_key = _staff_key_from_actor(event)
    if not settings.is_scribe_modality(staff_key):
        return False

    # If allowed note types are configured, check the note's type.
    allowed_raw = secrets.get(Constants.SECRET_SCRIBE_NOTE_TYPES, "")
    allowed = [s.strip().lower() for s in allowed_raw.split(",") if s.strip()]
    if not allowed:
        return True

    note_dbid = event.context.get("note_id")
    if not note_dbid:
        return False
    try:
        note_type_name = Note.objects.values_list("note_type_version__name", flat=True).get(dbid=note_dbid)
        return (note_type_name or "").strip().lower() in allowed
    except Note.DoesNotExist:
        return False


def _scribe_tab_has_content(note_dbid: int) -> bool:
    """Return True when the Scribe tab has meaningful documentation.

    Used to decide whether to hide the tab on locked notes that were never
    used. Covers manual-mode users (who may have a ScribeSummary row from
    template selection but no actual content) by inspecting the persisted
    payloads instead of relying on row existence alone.
    """
    items = ScribeTranscript.objects.filter(note_id=note_dbid).values_list("items", flat=True).first()
    if items:
        return True

    summary = ScribeSummary.objects.filter(note_id=note_dbid).values("note_data", "commands", "approved").first()
    if not summary:
        return False
    if summary["approved"] or summary["commands"]:
        return True
    sections = (summary.get("note_data") or {}).get("sections") or []
    return any((s.get("text") or "").strip() for s in sections)


def is_debug_visible(secrets: dict[str, str], event: Event) -> bool:
    """Return True when debug apps (Audit, Cache) should be visible for this staff."""
    if not is_scribe_visible(secrets, event):
        return False
    allowed_raw = secrets.get(Constants.SECRET_SCRIBE_DEBUG_STAFFERS, "")
    allowed = [s.strip().lower() for s in allowed_raw.split(",") if s.strip()]
    if not allowed:
        return False
    staff_key = _staff_key_from_actor(event)
    return staff_key.lower() in allowed


class ScribeApp(NoteApplication):
    """Note application for Canvas Scribe with recording and transcript."""

    IDENTIFIER = "hyperscribe__scribe"
    PRIORITY = 0

    @property
    def NAME(self) -> str:
        return self.secrets.get(Constants.SECRET_SCRIBE_TAB_NAME) or "Scribe"

    def open_by_default(self) -> bool:
        # Defer to the legacy Canvas note tab when the note is locked AND the
        # Scribe tab was never used for documentation, so users land on the
        # canonical note instead of an empty Scribe surface. The tab itself
        # remains in the tab bar for users who want to inspect it.
        note_dbid = self.event.context.get("note_id")
        if note_dbid and not Helper.editable_note(note_dbid) and not _scribe_tab_has_content(note_dbid):
            return False
        return True

    def visible(self) -> bool:
        return is_scribe_visible(self.secrets, self.event)

    def handle(self) -> list[Effect]:
        note_dbid = self.context.get("note_id")
        note_id = Note.objects.values_list("id", flat=True).get(dbid=note_dbid)
        url = f"{Constants.PLUGIN_API_BASE_ROUTE}/scribe/app?note_id={note_id}&view=scribe"

        return [
            LaunchModalEffect(
                url=url,
                target=LaunchModalEffect.TargetType.NOTE,
                title=self.NAME,
            ).apply()
        ]
