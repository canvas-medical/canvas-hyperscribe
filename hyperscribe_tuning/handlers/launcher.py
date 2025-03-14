from hashlib import sha256
from time import time

from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note
from logger import log

from hyperscribe_tuning.handlers.constants import Constants


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
        interval = self.secrets[Constants.SECRET_AUDIO_INTERVAL_SECONDS]
        note_id = str(Note.objects.get(dbid=self.event.context['note_id']).id)
        patient_id = self.target

        ts = str(int(time()))
        hash_arg = ts + self.secrets[Constants.SECRET_API_SIGNING_KEY]
        sig = sha256(hash_arg.encode('utf-8')).hexdigest()
        params = f"note_id={note_id}&patient_id={patient_id}&interval={interval}&ts={ts}&sig={sig}"
        tuning_ui = LaunchModalEffect(
            url=f"/plugin-io/api/hyperscribe_tuning/capture-case?{params}",
            target=LaunchModalEffect.TargetType.NEW_WINDOW,
        )
        return [tuning_ui.apply()]

    def visible(self) -> bool:
        return True
