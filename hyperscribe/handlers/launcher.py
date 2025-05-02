from urllib.parse import urlencode

from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.v1.data.note import Note

from hyperscribe.handlers.constants import Constants


class Launcher(ActionButton):
    BUTTON_TITLE = "🖊️ Hyperscribe"
    BUTTON_KEY = "HYPERSCRIBE_LAUNCHER"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER

    RESPONDS_TO = [
        EventType.Name(EventType.SHOW_NOTE_HEADER_BUTTON),
        EventType.Name(EventType.ACTION_BUTTON_CLICKED)
    ]

    def handle(self) -> list[Effect]:
        audio_server_base_url = self.secrets[Constants.SECRET_AUDIO_HOST].rstrip('/')
        interval = self.secrets[Constants.SECRET_AUDIO_INTERVAL]
        note_id = str(Note.objects.get(dbid=self.event.context['note_id']).id)
        patient_id = self.target

        canvas_instance = self.environment[Constants.CUSTOMER_IDENTIFIER].strip()
        aws_s3_region = self.secrets[Constants.SECRET_AWS_REGION]
        progress = f"https://{Constants.INFORMANT_AWS_BUCKET}.s3.{aws_s3_region}.amazonaws.com/{canvas_instance}/progresses/{patient_id}.log"
        end_flag = Constants.INFORMANT_END_OF_MESSAGES

        encoded_params = urlencode({
            "interval": interval,
            "end_flag": end_flag,
            "progress": progress,
        })

        hyperscribe_pane = LaunchModalEffect(
            url=f"{audio_server_base_url}/capture/{patient_id}/{note_id}?{encoded_params}",
            target=LaunchModalEffect.TargetType.RIGHT_CHART_PANE
        )
        return [hyperscribe_pane.apply()]

    def visible(self) -> bool:
        return True
