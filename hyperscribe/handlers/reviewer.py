import json

from canvas_sdk.effects import Effect
from canvas_sdk.effects.launch_modal import LaunchModalEffect
from canvas_sdk.events import EventType
from canvas_sdk.handlers.action_button import ActionButton
from canvas_sdk.templates import render_to_string
from canvas_sdk.v1.data.note import Note

from hyperscribe.handlers.aws_s3 import AwsS3
from hyperscribe.handlers.constants import Constants
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.settings import Settings


class Reviewer(ActionButton):
    BUTTON_TITLE = "📖 Reviewer"
    BUTTON_KEY = "HYPERSCRIBE_REVIEWER"
    BUTTON_LOCATION = ActionButton.ButtonLocation.NOTE_HEADER

    RESPONDS_TO = [
        EventType.Name(EventType.SHOW_NOTE_HEADER_BUTTON),
        EventType.Name(EventType.ACTION_BUTTON_CLICKED)
    ]

    def handle(self) -> list[Effect]:
        note = Note.objects.get(dbid=self.event.context['note_id'])

        identification = IdentificationParameters(
            patient_uuid=note.patient.id,
            note_uuid=str(note.id),
            provider_uuid=str(note.provider.id),
            canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
        )
        credentials = AwsS3Credentials.from_dictionary(self.secrets)
        client_s3 = AwsS3(credentials)
        url_list = []
        if client_s3.is_ready() is True:
            store_path = (f"{identification.canvas_instance}/"
                          "audits/"
                          f"{identification.note_uuid}/")
            for document in client_s3.list_s3_objects(store_path):
                url_list.append(client_s3.generate_presigned_url(document.key, Constants.AWS3_LINK_EXPIRATION_SECONDS))

        hyperscribe_pane = LaunchModalEffect(
            content=render_to_string("handlers/reviewer.html", {"url_list": json.dumps(url_list)}),
            target=LaunchModalEffect.TargetType.DEFAULT_MODAL,
        )
        return [hyperscribe_pane.apply()]

    def visible(self) -> bool:
        settings = Settings.from_dictionary(self.secrets)
        return settings.audit_llm
