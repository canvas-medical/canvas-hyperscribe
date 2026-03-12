from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import NoteApplication

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.settings import Settings


class ScribeCacheApp(NoteApplication):
    """Note application for Canvas Scribe with recording and transcript."""

    NAME = "Cache"
    IDENTIFIER = "hyperscribe__scribe_cache"
    PRIORITY = 1

    def visible(self) -> bool:
        # PILOT: revert to `self.secrets.get(Constants.SECRET_MODALITY, "").lower() == Constants.MODALITY_SCRIBE`
        settings = Settings.from_dictionary(self.secrets)
        staff_id = self.context.get("user", {}).get("id", "")
        return settings.is_scribe_modality(staff_id)

    def handle(self) -> list[Effect]:
        from canvas_sdk.v1.data.note import Note

        note_dbid = self.context.get("note_id")
        note_id = Note.objects.values_list("id", flat=True).get(dbid=note_dbid)
        url = f"{Constants.PLUGIN_API_BASE_ROUTE}/scribe/app?note_id={note_id}&view=debug"

        return [
            LaunchModalEffect(
                url=url,
                target=LaunchModalEffect.TargetType.NOTE,
                title="Scribe Debug Cache",
            ).apply()
        ]
