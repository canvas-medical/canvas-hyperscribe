import json

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import NoteApplication
from canvas_sdk.v1.data.note import Note

from canvas_sdk.events import Event
from canvas_sdk.v1.data.staff import Staff

from hyperscribe.libraries.constants import Constants
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

    NAME = "Scribe"
    IDENTIFIER = "hyperscribe__scribe"
    PRIORITY = 0

    def open_by_default(self) -> bool:
        """Return True when no transcript has been saved yet or it hasn't been finalized."""
        try:
            note_dbid = self.context.get("note_id")
            note_id = Note.objects.values_list("id", flat=True).get(dbid=note_dbid)
            cache = get_cache()
            raw = cache.get(f"{_CACHE_KEY_PREFIX}{note_id}")

            if raw is None:
                return True

            data = json.loads(raw)
            return not data.get("finalized", False)

        except Exception:
            return False

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
                title="Scribe",
            ).apply()
        ]
