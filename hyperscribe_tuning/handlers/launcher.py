from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note
from canvas_sdk.templates import render_to_string

from logger import log

class Launcher(ActionButton):
    BUTTON_TITLE = "🧪 Hyperscribe Tuning"
    BUTTON_KEY = "HYPERSCRIBE_TUNING_LAUNCHER"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER
    
    RESPONDS_TO = [
        EventType.Name(EventType.SHOW_NOTE_HEADER_BUTTON),
        EventType.Name(EventType.ACTION_BUTTON_CLICKED)
    ]

    def handle(self) -> list[Effect]:
        log.info('Handling button click')
        interval = self.secrets['AudioIntervalSeconds']
        note_id = str(Note.objects.get(dbid=self.event.context['note_id']).id)
        patient_id = self.target

        # TODO Decide whether to serve this from custom API
        template_context = {
            'note_id': note_id,
            'patient_id': patient_id,
            'interval': interval
        }
        hyperscribe_pane = LaunchModalEffect(
            content=render_to_string(
                'templates/capture_tuning_case.html', template_context),
            target=LaunchModalEffect.TargetType.RIGHT_CHART_PANE
        )
        return [hyperscribe_pane.apply()]

    def visible(self) -> bool:
        return True
