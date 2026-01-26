from datetime import datetime, UTC
from http import HTTPStatus

from canvas_sdk.caching.plugins import get_cache
from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response, HTMLResponse, JSONResponse
from canvas_sdk.handlers.base import version
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPI, api
from canvas_sdk.templates import render_to_string
from canvas_sdk.utils.http import ThreadPoolExecutor
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log
from requests import post as requests_post

from hyperscribe.handlers.progress_display import ProgressDisplay
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.customization import Customization
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.llm_decisions_reviewer import LlmDecisionsReviewer
from hyperscribe.libraries.llm_turns_store import LlmTurnsStore
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.libraries.stop_and_go import StopAndGo
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.cycle_data import CycleData
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.notion_feedback_record import NotionFeedbackRecord
from hyperscribe.structures.progress_message import ProgressMessage
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.webm_prefix import WebmPrefix

executor = ThreadPoolExecutor(max_workers=50)


class CaptureView(SimpleAPI):
    PREFIX = None

    def authenticate(self, credentials: Credentials) -> bool:
        return Authenticator.check(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            Constants.API_SIGNED_EXPIRATION_SECONDS,
            self.request.query_params,
        )

    def trigger_render(self, patient_id: str, note_id: str, user_id: str) -> Response:
        host = Helper.canvas_host(self.environment[Constants.CUSTOMER_IDENTIFIER])
        url = Authenticator.presigned_url_no_params(
            Settings.from_dictionary(self.secrets).api_signing_key,
            f"{host}{Constants.PLUGIN_API_BASE_ROUTE}/capture/render/{patient_id}/{note_id}/{user_id}",
        )
        return requests_post(url, headers={"Content-Type": "application/json"}, verify=True, timeout=None)

    def session_progress_log(self, patient_id: str, note_id: str, progress: str) -> None:
        identification = IdentificationParameters(
            patient_uuid=patient_id,
            note_uuid=note_id,
            provider_uuid="",
            canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
        )
        settings = Settings.from_dictionary(self.secrets | {Constants.PROGRESS_SETTING_KEY: True})
        messages = [ProgressMessage(message=progress, section=Constants.PROGRESS_SECTION_EVENTS)]
        ProgressDisplay.send_to_user(identification, settings, messages)
        log.info(f"progress: {progress} sent")

    @api.get("/capture/<patient_id>/<note_id>/<note_reference>")
    def capture_get(self) -> list[Response | Effect]:
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        note_reference = self.request.path_params["note_reference"]
        user_id = self.request.headers.get("canvas-logged-in-user-id")

        progress_url = Authenticator.presigned_url(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/progress",
            {"note_id": note_id},
        )

        new_session_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/capture/new-session/{patient_id}/{note_id}",
        )
        pause_session_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/capture/idle/{patient_id}/{note_id}/{Constants.AUDIO_IDLE_PAUSE}",
        )
        resume_session_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/capture/idle/{patient_id}/{note_id}/{Constants.AUDIO_IDLE_RESUME}",
        )
        end_session_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/capture/idle/{patient_id}/{note_id}/{Constants.AUDIO_IDLE_END}",
        )
        feedback_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/feedback/{patient_id}/{note_id}",
        )
        save_audio_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/audio/{patient_id}/{note_id}",
        )
        save_transcript_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/transcript/{patient_id}/{note_id}",
        )
        draft_transcript_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/draft/{patient_id}/{note_id}",
        )
        ws_progress_url = (
            f"{Helper.canvas_ws_host(self.environment[Constants.CUSTOMER_IDENTIFIER])}"
            f"{Constants.PLUGIN_WS_BASE_ROUTE}/{ProgressDisplay.websocket_channel(note_id)}/"
        )

        customization = Customization.customizations(
            AwsS3Credentials.from_dictionary(self.secrets),
            self.environment[Constants.CUSTOMER_IDENTIFIER],
            user_id,
        )

        stop_and_go = StopAndGo.get(note_id)
        context = {
            "patientUuid": patient_id,
            "noteUuid": note_id,
            "noteReference": note_reference,
            "userUuid": user_id,
            "interval": self.secrets[Constants.SECRET_AUDIO_INTERVAL],
            "endFlag": Constants.PROGRESS_END_OF_MESSAGES,
            "wsProgressURL": ws_progress_url,
            "progressURL": progress_url,
            "newSessionURL": new_session_url,
            "pauseSessionURL": pause_session_url,
            "resumeSessionURL": resume_session_url,
            "endSessionURL": end_session_url,
            "feedbackURL": feedback_url,
            "saveAudioURL": save_audio_url,
            "saveTranscriptURL": save_transcript_url,
            "draftTranscriptURL": draft_transcript_url,
            "isEnded": stop_and_go.is_ended(),
            "isPaused": stop_and_go.is_paused(),
            "chunkId": stop_and_go.cycle() + (1 if stop_and_go.is_paused() else -1),
            "uiDefaultTab": customization.ui_default_tab.value,
        }

        return [
            HTMLResponse(
                render_to_string("templates/hyperscribe.html", context),
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/capture/new-session/<patient_id>/<note_id>")
    def new_session_post(self) -> list[Response | Effect]:
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        self.session_progress_log(patient_id, note_id, "started")
        return []

    @api.post("/capture/idle/<patient_id>/<note_id>/<action>")
    def idle_session_post(self) -> list[Response | Effect]:
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        action = self.request.path_params["action"]

        stop_and_go = StopAndGo.get(note_id)
        if not stop_and_go.is_ended() and action == Constants.AUDIO_IDLE_END:
            stop_and_go.set_ended(True).save()
            self.session_progress_log(patient_id, note_id, "stopped")
        elif stop_and_go.is_paused() and action == Constants.AUDIO_IDLE_RESUME:
            stop_and_go.set_paused(False).save()
            self.session_progress_log(patient_id, note_id, "resumed")
        elif not stop_and_go.is_paused() and action == Constants.AUDIO_IDLE_PAUSE:
            stop_and_go.set_paused(True).save()
            self.session_progress_log(patient_id, note_id, "paused")
        return []

    @api.post("/audio/<patient_id>/<note_id>")
    def audio_chunk_post(self) -> list[Response | Effect]:
        form_data = self.request.form_data()
        if "audio" not in form_data:
            return [Response(b"No audio file part in the request", HTTPStatus.BAD_REQUEST)]

        audio_form_part = form_data["audio"]
        if not audio_form_part.is_file():
            return [Response(b"The audio form part is not a file", HTTPStatus.UNPROCESSABLE_ENTITY)]

        log.info(f"audio_form_part.name: {audio_form_part.name}")
        log.info(f"audio_form_part.filename: {audio_form_part.filename}")
        log.info(f"len(audio_form_part.content): {len(audio_form_part.content)}")
        log.info(f"audio_form_part.content_type: {audio_form_part.content_type}")

        content = audio_form_part.content
        content_type = audio_form_part.content_type
        if not audio_form_part.filename.startswith("chunk_000_"):
            content = WebmPrefix.add_prefix(audio_form_part.content)
        return self._add_cycle(content, content_type)

    @api.post("/transcript/<patient_id>/<note_id>")
    def transcript_chunk_post(self) -> list[Response | Effect]:
        form_data = self.request.form_data()
        content = form_data.get("transcript").value.encode()
        content_type = CycleData.content_type_text()
        return self._add_cycle(content, content_type)

    def _draft_key(self) -> str:
        patient_uuid = self.request.path_params["patient_id"]
        note_uuid = self.request.path_params["note_id"]
        return f"draft_{patient_uuid}_{note_uuid}"

    @api.post("/draft/<patient_id>/<note_id>")
    def draft_chunk_post(self) -> list[Response | Effect]:
        form_data = self.request.form_data()
        content = form_data.get("transcript").value
        get_cache().set(self._draft_key(), content)
        return [Response(status_code=HTTPStatus.CREATED)]

    @api.get("/draft/<patient_id>/<note_id>")
    def draft_chunk_get(self) -> list[Response | Effect]:
        return [JSONResponse(content={"draft": get_cache().get(self._draft_key()) or ""}, status_code=HTTPStatus.OK)]

    def _add_cycle(self, content: bytes, content_type: str) -> list[Response | Effect]:
        identification = IdentificationParameters(
            patient_uuid=self.request.path_params["patient_id"],
            note_uuid=self.request.path_params["note_id"],
            provider_uuid=str(Note.objects.get(id=self.request.path_params["note_id"]).provider.id),
            canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
        )
        stop_and_go = StopAndGo.get(identification.note_uuid)
        stop_and_go.add_waiting_cycle().save()
        cycle = stop_and_go.waiting_cycles()[-1]

        aws_s3 = AwsS3Credentials.from_dictionary(self.secrets)
        path_s3 = CycleData.s3_key_path(identification, cycle)
        response = AwsS3(aws_s3).upload_binary_to_s3(path_s3, content, content_type)
        if response.status_code != HTTPStatus.OK:
            log.info(f"Failed to save chunk {cycle} with status {response.status_code}: {str(response.content)}")
            if not response.status_code:
                return [Response(b"Failed to save chunk (AWS S3 failure)", HTTPStatus.SERVICE_UNAVAILABLE)]
            return [Response(response.content, HTTPStatus(response.status_code))]
        if not stop_and_go.is_running():
            user_id = self.request.headers.get("canvas-logged-in-user-id")
            executor.submit(Helper.with_cleanup(self.run_commander), identification, user_id)

        return [Response(f"Chunk {cycle} saved OK".encode(), HTTPStatus.CREATED)]

    @api.post("/capture/render/<patient_id>/<note_id>/<user_id>")
    def render_effect_post(self) -> list[Response | Effect]:
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        user_id = self.request.path_params["user_id"]

        stop_and_go = StopAndGo.get(note_id)
        if effects := stop_and_go.paused_effects():
            stop_and_go.reset_paused_effect().set_delay().save()
            return effects
        return []

    @api.post("/feedback/<patient_id>/<note_id>")
    def feedback_post(self) -> list[Response | Effect]:
        note_id = self.request.path_params["note_id"]
        form_data = self.request.form_data()
        feedback = form_data.get("feedback")
        if not (feedback and feedback.value):
            return [Response(b"Feedback cannot be empty", HTTPStatus.BAD_REQUEST)]

        aws_credentials = AwsS3Credentials.from_dictionary(self.secrets)
        client_s3 = AwsS3(aws_credentials)
        if not client_s3.is_ready():
            return [Response(b"Storage is not made available", HTTPStatus.INTERNAL_SERVER_ERROR)]

        canvas_instance = self.environment[Constants.CUSTOMER_IDENTIFIER]
        now = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
        store_path = f"hyperscribe-{canvas_instance}/feedback/{note_id}/{now}"
        client_s3.upload_text_to_s3(store_path, feedback.value)  # feedback is a StringFormPart

        notion_feedback = NotionFeedbackRecord(
            instance=canvas_instance,
            note_uuid=note_id,
            date_time=now,
            feedback=feedback.value,
        )
        url = Constants.VENDOR_NOTION_API_BASE_URL
        headers = {
            "Authorization": f"Bearer {self.secrets[Constants.SECRET_NOTION_API_KEY]}",
            "Content-Type": "application/json",
            "Notion-Version": Constants.VENDOR_NOTION_API_VERSION,
        }
        data = notion_feedback.to_json(self.secrets[Constants.SECRET_NOTION_FEEDBACK_DATABASE_ID])
        resp = requests_post(url, headers=headers, data=data)
        log.info(f"Notion response status: {resp.status_code}")
        if resp.status_code != 200:
            # Raise this directly so that Sentry alerts us
            # Background: https://github.com/canvas-medical/canvas-hyperscribe/issues/111
            # End user will see "Error: Server error: 500" and that is fine
            log.info(f"Notion response status {resp.status_code}, text: {resp.text}")
            raise RuntimeError(f"Feedback failed to save via Notion API, status {resp.status_code}, text: {resp.text}")

        return [Response(b"Feedback saved OK", HTTPStatus.CREATED)]

    def run_reviewer(self, identification: IdentificationParameters, created: datetime, cycles: int) -> None:
        settings = Settings.from_dictionary(self.secrets | {Constants.PROGRESS_SETTING_KEY: True})
        if settings.audit_llm:
            log.info(f"  => final audit started...{identification.note_uuid} / {cycles} cycles")
            credentials = AwsS3Credentials.from_dictionary(self.secrets)
            mapping = ImplementedCommands.schema_key2instruction()
            command2uuid = {
                LlmTurnsStore.indexed_instruction(mapping[command.schema_key], index): str(command.id)
                for index, command in enumerate(
                    Command.objects.filter(
                        patient__id=identification.patient_uuid,
                        note__id=identification.note_uuid,
                        state="staged",  # <--- TODO use an Enum when provided
                    ).order_by("dbid"),
                )
            }
            LlmDecisionsReviewer.review(identification, settings, credentials, command2uuid, created, cycles)
            log.info(f"  => final audit done ({identification.note_uuid} / {cycles} cycles)")
        # end the flow
        self.session_progress_log(
            identification.patient_uuid,
            identification.note_uuid,
            Constants.PROGRESS_END_OF_MESSAGES,
        )

    def run_commander(self, identification: IdentificationParameters, user_id: str) -> None:
        # add the running flag
        stop_and_go = StopAndGo.get(identification.note_uuid)
        if stop_and_go.is_running():
            return
        stop_and_go.set_running(True).save()
        try:
            aws_s3 = AwsS3Credentials.from_dictionary(self.secrets)
            settings = Settings.from_dictionary(
                self.secrets
                | Customization.custom_prompts_as_secret(
                    aws_s3,
                    self.environment[Constants.CUSTOMER_IDENTIFIER],
                    user_id,
                )
                | {Constants.PROGRESS_SETTING_KEY: True}
            )
            MemoryLog.instance(identification, Constants.MEMORY_LOG_LABEL, aws_s3).output(
                f"SDK: {version} - "
                f"Text: {settings.llm_text.vendor} - "
                f"Audio: {settings.llm_audio.vendor} - "
                f"Workers: {settings.max_workers}"
            )

            while True:
                stop_and_go = StopAndGo.get(identification.note_uuid)
                if not stop_and_go.consume_next_waiting_cycles(True):
                    break
                # stop_and_go.consume_delay()
                # from canvas_sdk.clients.waiter import Waiter
                # Waiter.sleep_for(40)
                # effects = []
                had_audio, effects = Commander.compute_cycle(identification, settings, aws_s3, stop_and_go.cycle())

                # store the effects to be rendered
                if effects:
                    stop_and_go = StopAndGo.get(identification.note_uuid)
                    stop_and_go.add_paused_effects(effects).save()
                    # request the rendering
                    self.trigger_render(identification.patient_uuid, identification.note_uuid, user_id)
                # clean up and messages
                MemoryLog.end_session(identification.note_uuid)
                LlmTurnsStore.end_session(identification.note_uuid)

        except Exception as e:
            log.info("************************")
            log.error(f"Error while running commander: {e}", exc_info=True)
            log.info("************************")
        finally:
            stop_and_go = StopAndGo.get(identification.note_uuid)
            # remove the running flag
            stop_and_go.set_running(False).save()
            # if finished, run the reviewer
            if stop_and_go.is_ended():
                self.session_progress_log(identification.patient_uuid, identification.note_uuid, "finished")
                self.run_reviewer(identification, stop_and_go.created(), stop_and_go.cycle())
