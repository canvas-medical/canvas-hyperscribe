from __future__ import annotations

from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.application import NoteApplication
from canvas_sdk.v1.data.note import Note

from hyperscribe.libraries.constants import Constants
from hyperscribe.scribe.application.transcript_app import is_debug_visible


class ScribeAuditApp(NoteApplication):
    NAME = "Audit"
    IDENTIFIER = "hyperscribe__scribe_audit"
    PRIORITY = 2

    def visible(self) -> bool:
        return is_debug_visible(self.secrets, self.event)

    def handle(self) -> list[Effect]:
        note_dbid = self.context.get("note_id")
        note_id = Note.objects.values_list("id", flat=True).get(dbid=note_dbid)
        url = f"{Constants.PLUGIN_API_BASE_ROUTE}/scribe/app?note_id={note_id}&view=audit"
        return [
            LaunchModalEffect(
                url=url,
                target=LaunchModalEffect.TargetType.NOTE,
                title="Scribe Audit Log",
            ).apply()
        ]
