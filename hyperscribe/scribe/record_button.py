from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton

from hyperscribe.libraries.constants import Constants


class RecordButton(ActionButton):
    """Action button in the note header to open the recording panel."""

    BUTTON_TITLE = "Record"
    BUTTON_KEY = "SCRIBE_RECORD"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER

    RESPONDS_TO = [
        EventType.Name(EventType.SHOW_NOTE_HEADER_BUTTON),
        EventType.Name(EventType.ACTION_BUTTON_CLICKED),
    ]

    def visible(self) -> bool:
        modality = self.secrets.get(Constants.SECRET_MODALITY, "").lower()
        return bool(modality == Constants.MODALITY_SCRIBE)

    def handle(self) -> list[Effect]:
        note_id = self.event.context["note_id"]
        url = f"{Constants.PLUGIN_API_BASE_ROUTE}/scribe/app?note_dbid={note_id}&view=record"

        return [
            LaunchModalEffect(
                url=url,
                target=LaunchModalEffect.TargetType.RIGHT_CHART_PANE,
                title="Record",
            ).apply()
        ]
