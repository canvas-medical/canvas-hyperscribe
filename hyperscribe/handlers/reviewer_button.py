from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note, CurrentNoteStateEvent

from hyperscribe.libraries.authenticator import Authenticator
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
        presigned_url = Authenticator.presigned_url(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            "/plugin-io/api/hyperscribe/reviewer",
            {
                "patient_id": str(note.patient.id),
                "note_id": str(note.id),
            },
        )
        hyperscribe_pane = LaunchModalEffect(
            url=presigned_url,
            target=LaunchModalEffect.TargetType.NEW_WINDOW,
        )
        return [hyperscribe_pane.apply()]

    def visible(self) -> bool:
        settings = Settings.from_dictionary(self.secrets)
        staff_id = self.context.get("user", {}).get("id", "")
        result = False
        if settings.audit_llm and (not settings.is_tuning) and settings.staffers_policy.is_allowed(staff_id):
            result = CurrentNoteStateEvent.objects.get(note_id=self.event.context['note_id']).editable()
        return result
