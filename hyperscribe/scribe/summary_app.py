from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import NoteApplication

from hyperscribe.libraries.constants import Constants


class SummaryApp(NoteApplication):
    """Note application that displays the visit summary."""

    NAME = "Summary"
    IDENTIFIER = "hyperscribe__scribe_summary"

    def visible(self) -> bool:
        modality = self.secrets.get(Constants.SECRET_MODALITY, "").lower()
        return bool(modality == Constants.MODALITY_SCRIBE)

    def handle(self) -> list[Effect]:
        note_id = self.context.get("note_id")
        url = f"{Constants.PLUGIN_API_BASE_ROUTE}/scribe/app?note_dbid={note_id}&view=summary"

        return [
            LaunchModalEffect(
                url=url,
                target=LaunchModalEffect.TargetType.NOTE,
                title="Summary",
            ).apply()
        ]
