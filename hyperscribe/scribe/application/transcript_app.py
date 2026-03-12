import json

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import NoteApplication
from canvas_sdk.v1.data.note import Note

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.settings import Settings

_CACHE_KEY_PREFIX = "scribe_transcript:"


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
        # PILOT: revert to `self.secrets.get(Constants.SECRET_MODALITY, "").lower() == Constants.MODALITY_SCRIBE`
        settings = Settings.from_dictionary(self.secrets)
        staff_id = self.context.get("user", {}).get("id", "")
        return settings.is_scribe_modality(staff_id)

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
