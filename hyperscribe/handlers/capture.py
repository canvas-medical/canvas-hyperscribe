import json

from http import HTTPStatus

from datetime import datetime
from time import time

from logger import log

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response, HTMLResponse
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPI, api
from canvas_sdk.templates import render_to_string
from canvas_sdk.utils.http import Http
from canvas_sdk.v1.data.staff import Staff

from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.audio_client import AudioClient


class CaptureView(SimpleAPI):
    PREFIX = None

    def authenticate(self, credentials: Credentials) -> bool:
        return Authenticator.check(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            Constants.API_SIGNED_EXPIRATION_SECONDS,
            self.request.query_params,
        )

    @api.get("/capture/<patient_id>/<note_id>")
    def capture_get(self) -> list[Response | Effect]:
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        
        progress_url = Authenticator.presigned_url(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.BASE_ROUTE}/progress",
            {"note_id": note_id},
        )

        new_session_url = Authenticator.presigned_url(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.BASE_ROUTE}/capture/new-session/{patient_id}/{note_id}"
        )

        save_audio_url = Authenticator.presigned_url(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.BASE_ROUTE}/audio/{patient_id}/{note_id}"
        )

        context = {
            'patientUuid': patient_id, 
            'noteUUID': note_id,
            'interval': self.secrets[Constants.SECRET_AUDIO_INTERVAL],
            'endFlag': Constants.PROGRESS_END_OF_MESSAGES,
            'progressURL': progress_url,
            'newSessionURL': new_session_url,
            'saveAudioURL': save_audio_url,
        }

        return [
            HTMLResponse(
                render_to_string('templates/hyperscribe.html', context),
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/capture/new-session/<patient_id>/<note_id>")
    def new_session_post(self) -> list[Response | Effect]:
        # 1. Get a user token
        # 2. Create a new session
        # 3. Create a new task (to trigger the commander)

        audio_client = AudioClient(
            base_url=self.secrets[Constants.SECRET_AUDIO_HOST],
            instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
            instance_key=self.secrets[Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY]
        )

        logged_in_user_id = self.request.headers.get("canvas-logged-in-user-id")
        user_token = audio_client.get_user_token(logged_in_user_id)
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        session_id = audio_client.create_session(user_token, {
            'note_id': note_id, 
            'patient_id': patient_id, 
        })

        audio_client.add_session(patient_id, note_id, session_id, logged_in_user_id, user_token)

        team_id = self.secrets[Constants.COPILOTS_TEAM_FHIR_GROUP_ID]
        # team_id = Team.objects.get(name='Copilots').id
        # The above doesn't work because the FHIR group id is not the team.id
        # and the FHIR group id is not exposed in the data model :/

        staff_id = Staff.objects.get(dbid=1).id
        comment_text = json.dumps({
            'note_id': note_id, 
            'patient_id': patient_id, 
            'chunk_index': 1
        })

        # TODO: handle timezone, this appears wrong in the UI, 
        # creation time is off by 5 hours
        now_timestamp = datetime.now().isoformat() + '+00:00'

        headers = {'Authorization': f'Bearer {self.secrets[Constants.FUMAGE_BEARER_TOKEN]}'}
        url = f"https://fumage-{self.environment[Constants.CUSTOMER_IDENTIFIER]}.canvasmedical.com/Task"
        payload = {
            "resourceType":
            "Task",
            "extension": [{
                "url": "http://schemas.canvasmedical.com/fhir/extensions/task-group",
                "valueReference": {"reference": f"Group/{team_id}"}
            }],
            "status": "requested",
            "intent": "unknown",
            "description": "Encounter Copilot",
            "for": {"reference": f"Patient/{patient_id}"},
            "authoredOn": now_timestamp,
            "requester": {"reference": f"Practitioner/{staff_id}"},
            "owner": {"reference": f"Practitioner/{staff_id}"},
            "note": [{
                "authorReference": {"reference": f"Practitioner/{staff_id}"},
                "time": now_timestamp,
                "text": comment_text
            }],
            "input": [{"type": {"text": "label"}, "valueString": "Encounter Copilot"}]
        }
        t0 = time()
        http = Http()
        response = http.post(url, json=payload, headers=headers)
        log.info(f'FHIR Task Create duration: {int(100*(time()-t0))/100} seconds')
        return [Response(response.content, response.status_code)]

    @api.post("/audio/<patient_id>/<note_id>")
    def audio_chunk_post(self) -> list[Response | Effect]:       
        form_data = self.request.form_data()
        if 'audio' not in form_data:
            return Response(b"No audio file part in the request", 400)
        
        audio_form_part = form_data['audio']
        if not audio_form_part.is_file():
            return Response(b"The audio form part is not a file", 422)

        log.info(f"audio_form_part.name: {audio_form_part.name}")
        log.info(f"audio_form_part.filename: {audio_form_part.filename}")
        log.info(f"len(audio_form_part.content): {len(audio_form_part.content)}")
        log.info(f"audio_form_part.content_type: {audio_form_part.content_type}")

        audio_client = AudioClient(
            base_url=self.secrets[Constants.SECRET_AUDIO_HOST],
            instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
            instance_key=self.secrets[Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY]
        )
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]       
        response = audio_client.save_audio_chunk(patient_id, note_id, audio_form_part)
        
        if response.status_code != 201:
            log.info(f'Failed to save chunk with status {response.status_code}: {response.content}')
            return [Response(response.content, response.status_code)]
        
        return [Response(b"Audio chunk saved OK", 201)]
