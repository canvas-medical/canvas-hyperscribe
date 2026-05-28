from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.action_button import ActionButton

from hyperscribe.libraries.constants import Constants
from hyperscribe.scribe.application.transcript_app import is_scribe_visible


class PrintScribeNoteButton(ActionButton):
    """Note header dropdown button that launches a print preview of the scribe summary."""

    BUTTON_TITLE = "🖨️ Print Scribe Note"
    BUTTON_KEY = "HYPERSCRIBE_PRINT_SCRIBE_NOTE"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER_DROPDOWN

    def visible(self) -> bool:
        return is_scribe_visible(self.secrets, self.event)

    def handle(self) -> list[Effect]:
        note_id = self.event.context["note_id"]
        url = f"{Constants.PLUGIN_API_BASE_ROUTE}/scribe-print/note/{note_id}"
        return [
            LaunchModalEffect(
                url=url,
                target=LaunchModalEffect.TargetType.DEFAULT_MODAL,
                title="Print Scribe Note",
            ).apply()
        ]
