from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import NoteApplication

from hyperscribe.libraries.constants import Constants


class ScribeApp(NoteApplication):
    """Note application for Canvas Scribe with recording and transcript."""

    NAME = "Scribe"
    IDENTIFIER = "hyperscribe__scribe"

    def visible(self) -> bool:
        modality = self.secrets.get(Constants.SECRET_MODALITY, "").lower()
        return bool(modality == Constants.MODALITY_SCRIBE)

    def handle(self) -> list[Effect]:
        from canvas_sdk.v1.data.note import Note

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
