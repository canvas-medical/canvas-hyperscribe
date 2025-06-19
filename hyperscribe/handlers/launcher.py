from urllib.parse import urlencode

from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note

from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.settings import Settings


class Launcher(ActionButton):
    BUTTON_TITLE = "🖊️ Hyperscribe"
    BUTTON_KEY = "HYPERSCRIBE_LAUNCHER"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER

    RESPONDS_TO = [
        EventType.Name(EventType.SHOW_NOTE_HEADER_BUTTON),
        EventType.Name(EventType.ACTION_BUTTON_CLICKED)
    ]

    def handle(self) -> list[Effect]:
        note_id = str(Note.objects.get(dbid=self.event.context['note_id']).id)
        audio_server_base_url = self.secrets[Constants.SECRET_AUDIO_HOST].rstrip('/')
        patient_id = self.target
        identification = IdentificationParameters(
            patient_uuid=patient_id,
            note_uuid=note_id,
            provider_uuid='N/A',  # this field is not used within this handle() method
            canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
        )
        encoded_params = urlencode({
            "interval": self.secrets[Constants.SECRET_AUDIO_INTERVAL],
            "end_flag": Constants.PROGRESS_END_OF_MESSAGES,
            "progress": Authenticator.presigned_url(
                self.secrets[Constants.SECRET_API_SIGNING_KEY],
                f"{identification.canvas_host()}/plugin-io/api/hyperscribe/progress",
                {"note_id": note_id},
            ),
        })
        hyperscribe_pane = LaunchModalEffect(
            url=f"{audio_server_base_url}/capture/{patient_id}/{note_id}?{encoded_params}",
            target=LaunchModalEffect.TargetType.RIGHT_CHART_PANE,
            title="Hyperscribe"
        )
        return [hyperscribe_pane.apply()]

    def visible(self) -> bool:
        settings = Settings.from_dictionary(self.secrets)
        staff_id = self.context.get("user", {}).get("id", "")
        return (not settings.is_tuning) and settings.staffers_policy.is_allowed(staff_id)
