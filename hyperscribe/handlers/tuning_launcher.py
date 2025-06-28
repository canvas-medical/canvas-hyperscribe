from hashlib import sha256
from time import time

from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.settings import Settings


class TuningLauncher(ActionButton):
    BUTTON_TITLE = "🧪 Hyperscribe Tuning"
    BUTTON_KEY = "HYPERSCRIBE_TUNING_LAUNCHER"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER

    RESPONDS_TO = [
        EventType.Name(EventType.SHOW_NOTE_HEADER_BUTTON),
        EventType.Name(EventType.ACTION_BUTTON_CLICKED)
    ]

    def handle(self) -> list[Effect]:
        interval = self.secrets[Constants.SECRET_AUDIO_INTERVAL]
        note_id = str(Note.objects.get(dbid=self.event.context['note_id']).id)
        patient_id = self.target

        # TODO: Use Authenticator here
        ts = str(int(time()))
        hash_arg = ts + self.secrets[Constants.SECRET_API_SIGNING_KEY]
        sig = sha256(hash_arg.encode('utf-8')).hexdigest()
        params = f"note_id={note_id}&patient_id={patient_id}&interval={interval}&ts={ts}&sig={sig}"
        tuning_ui = LaunchModalEffect(
            url=f"{Constants.BASE_ROUTE}/archive?{params}",
            target=LaunchModalEffect.TargetType.NEW_WINDOW,
        )
        return [tuning_ui.apply()]

    def visible(self) -> bool:
        settings = Settings.from_dictionary(self.secrets)
        staff_id = self.context.get("user", {}).get("id", "")
        return settings.is_tuning and settings.staffers_policy.is_allowed(staff_id)
