from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note


class HyperscribeLauncher(ActionButton):
    BUTTON_TITLE = "🖊️ Hyperscribe"
    BUTTON_KEY = "HYPERSCRIBE_LAUNCHER"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER

    def handle(self) -> list[Effect]:
        audio_server_base_url = self.secrets['AudioHost'].rstrip('/')
        interval = self.secrets['AudioIntervalSeconds']
        note_id = str(Note.objects.get(dbid=self.event.context['note_id']).id)
        patient_id = self.target
        hyperscribe_pane = LaunchModalEffect(
            url=f"{audio_server_base_url}/capture/{patient_id}/{note_id}?interval={interval}",
            target=LaunchModalEffect.TargetType.RIGHT_CHART_PANE
        )
        return [hyperscribe_pane.apply()]

    def visible(self) -> bool:
        return True
