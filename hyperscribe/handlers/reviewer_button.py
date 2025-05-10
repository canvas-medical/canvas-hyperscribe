from hashlib import sha256
from time import time

from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note

from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.settings import Settings


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
        presigned_url = self.presigned_url(str(note.patient.id), str(note.id), self.secrets[Constants.SECRET_AWS_SECRET])
        hyperscribe_pane = LaunchModalEffect(
            url=presigned_url,
            target=LaunchModalEffect.TargetType.NEW_WINDOW,
        )
        return [hyperscribe_pane.apply()]

    def visible(self) -> bool:
        settings = Settings.from_dictionary(self.secrets)
        return settings.audit_llm

    @classmethod
    def presigned_url(cls, patient_uuid: str, note_uuid: str, secret: str) -> str:
        timestamp = str(int(time()))
        hash_arg = f"{timestamp}{secret}"
        request_sig = sha256(hash_arg.encode('utf-8')).hexdigest()

        params = f"note_id={note_uuid}&patient_id={patient_uuid}&ts={timestamp}&sig={request_sig}"
        return f"/plugin-io/api/hyperscribe/reviewer?{params}"
