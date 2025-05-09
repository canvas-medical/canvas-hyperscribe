from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.settings import Settings
from hashlib import sha256
from time import time


class ReviewerButton(ActionButton):
    BUTTON_TITLE = "📖 Reviewer"
    BUTTON_KEY = "HYPERSCRIBE_REVIEWER"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER

    RESPONDS_TO = [
        EventType.Name(EventType.SHOW_NOTE_HEADER_BUTTON),
        EventType.Name(EventType.ACTION_BUTTON_CLICKED)
    ]

    def handle(self) -> list[Effect]:
        note = Note.objects.get(dbid=self.event.context['note_id'])

        timestamp = str(int(time()))
        hash_arg = f"{timestamp}{self.secrets[Constants.SECRET_AWS_SECRET]}"
        request_sig = sha256(hash_arg.encode('utf-8')).hexdigest()

        params = f"note_id={note.id}&patient_id={note.patient.id}&ts={timestamp}&sig={request_sig}"

        hyperscribe_pane = LaunchModalEffect(
            url=f"/plugin-io/api/hyperscribe/reviewer?{params}",
            target=LaunchModalEffect.TargetType.NEW_WINDOW,
        )
        return [hyperscribe_pane.apply()]

    def visible(self) -> bool:
        settings = Settings.from_dictionary(self.secrets)
        return settings.audit_llm
