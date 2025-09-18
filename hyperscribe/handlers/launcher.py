from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note, NoteStateChangeEvent, NoteStates
from canvas_sdk.v1.data.patient import Patient

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.settings import Settings

from logger import log


class Launcher(ActionButton):
    BUTTON_TITLE = "🖊️ Hyperscribe"
    BUTTON_KEY = "HYPERSCRIBE_LAUNCHER"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER

    RESPONDS_TO = [EventType.Name(EventType.SHOW_NOTE_HEADER_BUTTON), EventType.Name(EventType.ACTION_BUTTON_CLICKED)]

    def handle(self) -> list[Effect]:
        result: list[Effect] = []
        note_id = self.event.context["note_id"]
        note_uuid = str(Note.objects.get(dbid=note_id).id)
        patient_uuid = self.target

        presigned_url = Authenticator.presigned_url(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/capture/{patient_uuid}/{note_uuid}/{note_id}",
            {},
        )

        result.append(
            LaunchModalEffect(
                url=presigned_url,
                target=LaunchModalEffect.TargetType.RIGHT_CHART_PANE,
                title="Hyperscribe",
            ).apply()
        )
        return result

    def visible(self) -> bool:
        log.info(self.context)

        settings = Settings.from_dictionary(self.secrets)
        if settings.is_tuning:
            return False

        # DO NOT USE "CurrentStateChangeEvent" model. The view is too expensive.
        # It performs a max on id grouped by note for all notes, regardless of the note filter.
        current_note_state = (
            NoteStateChangeEvent.objects.filter(note_id=self.event.context["note_id"]).order_by("id").last()
        )
        note_is_editable = current_note_state and current_note_state.state in [
            NoteStates.NEW,
            NoteStates.PUSHED,
            NoteStates.UNLOCKED,
            NoteStates.RESTORED,
            NoteStates.UNDELETED,
            NoteStates.CONVERTED,
        ]
        if not note_is_editable:
            return False

        staff_id = self.context.get("user", {}).get("id", "")
        visibility = False
        if settings.staffers_policy.is_allowed(staff_id):
            visibility = True
        elif settings.trial_staffers_policy.is_allowed(staff_id):
            patient = Patient.objects.get(id=self.target)
            if patient.first_name.startswith(
                Constants.TRIAL_PATIENT_FIRST_NAME_STARTSWITH
            ) and patient.last_name.startswith(Constants.TRIAL_PATIENT_LAST_NAME_STARTSWITH):
                visibility = True

        if visibility:
            self.BUTTON_TITLE = f"🖊️ Hyperscribe ({self.event.context['note_id']})"

        return visibility
