import re
from datetime import datetime
from http import HTTPStatus

from canvas_sdk.effects import Effect
from canvas_sdk.effects.simple_api import Response, HTMLResponse
from canvas_sdk.handlers.base import version
from canvas_sdk.handlers.simple_api import Credentials, SimpleAPI, api
from canvas_sdk.templates import render_to_string
from canvas_sdk.utils.http import ThreadPoolExecutor
from canvas_sdk.v1.data.command import Command
from canvas_sdk.v1.data.note import Note
from logger import log

from hyperscribe.handlers.progress import Progress
from hyperscribe.libraries.audio_client import AudioClient
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.llm_decisions_reviewer import LlmDecisionsReviewer
from hyperscribe.libraries.llm_turns_store import LlmTurnsStore
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.libraries.stop_and_go import StopAndGo
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.settings import Settings

executor = ThreadPoolExecutor(max_workers=50)


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
        save_audio_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/audio/{patient_id}/{note_id}",
        )
        render_url = Authenticator.presigned_url_no_params(
            self.secrets[Constants.SECRET_API_SIGNING_KEY],
            f"{Constants.PLUGIN_API_BASE_ROUTE}/render/{patient_id}/{note_id}",
        )

        stop_and_go = StopAndGo.get(note_id)
        context = {
            "patientUuid": patient_id,
            "noteUuid": note_id,
            "interval": self.secrets[Constants.SECRET_AUDIO_INTERVAL],
            "endFlag": Constants.PROGRESS_END_OF_MESSAGES,
            "progressURL": progress_url,
            "newSessionURL": new_session_url,
            "pauseSessionURL": pause_session_url,
            "resumeSessionURL": resume_session_url,
            "endSessionURL": end_session_url,
            "saveAudioURL": save_audio_url,
            "renderURL": render_url,
            "isEnded": stop_and_go.is_ended(),
            "isPaused": stop_and_go.is_paused(),
            "chunkId": stop_and_go.cycle() + (1 if stop_and_go.is_paused() else -1),
        }

        return [
            HTMLResponse(
                render_to_string("templates/hyperscribe.html", context),
                status_code=HTTPStatus.OK,
            )
        ]

    @api.post("/capture/new-session/<patient_id>/<note_id>")
    def new_session_post(self) -> list[Response | Effect]:
        # 1. Get a user token
        # 2. Create a new session

        audio_client = AudioClient.for_operation(
            self.secrets[Constants.SECRET_AUDIO_HOST],
            self.environment[Constants.CUSTOMER_IDENTIFIER],
            self.secrets[Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY],
        )

        logged_in_user_id = self.request.headers.get("canvas-logged-in-user-id")
        user_token = audio_client.get_user_token(logged_in_user_id)
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        session_id = audio_client.create_session(
            user_token,
            {
                "note_id": note_id,
                "patient_id": patient_id,
            },
        )
        audio_client.add_session(patient_id, note_id, session_id, logged_in_user_id, user_token)
        return []

    @api.post("/capture/idle/<patient_id>/<note_id>/<action>")
    def idle_session_post(self) -> list[Response | Effect]:
        note_id = self.request.path_params["note_id"]
        action = self.request.path_params["action"]

        stop_and_go = StopAndGo.get(note_id)
        if not stop_and_go.is_ended() and action == Constants.AUDIO_IDLE_END:
            stop_and_go.set_ended(True).save()
        elif stop_and_go.is_paused() and action == Constants.AUDIO_IDLE_RESUME:
            stop_and_go.set_paused(False).save()
        elif not stop_and_go.is_paused() and action == Constants.AUDIO_IDLE_PAUSE:
            stop_and_go.set_paused(True).save()
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

        audio_client = AudioClient.for_operation(
            self.secrets[Constants.SECRET_AUDIO_HOST],
            self.environment[Constants.CUSTOMER_IDENTIFIER],
            self.secrets[Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY],
        )
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        response = audio_client.save_audio_chunk(patient_id, note_id, audio_form_part)

        if response.status_code != HTTPStatus.CREATED:
            log.info(f"Failed to save chunk with status {response.status_code}: {str(response.content)}")
            return [Response(response.content, HTTPStatus(response.status_code))]

        match = re.search(r"chunk_(\d+)_", audio_form_part.filename)
        if match:
            StopAndGo.get(note_id).add_waiting_cycle(int(match.group(1))).save()

        return [Response(b"Audio chunk saved OK", HTTPStatus.CREATED)]

    @api.post("/render/<patient_id>/<note_id>")
    def render_effect_post(self) -> list[Response | Effect]:
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]

        effects: list[Response | Effect] = []
        stop_and_go = StopAndGo.get(note_id)
        if paused := stop_and_go.paused_effects():
            effects.extend(paused)
            stop_and_go.reset_paused_effect().save()
        elif not stop_and_go.is_running():
            if stop_and_go.consume_next_waiting_cycles(True):
                executor.submit(
                    Helper.with_cleanup(self.run_commander),
                    patient_id,
                    note_id,
                    stop_and_go.cycle(),
                )
            elif stop_and_go.is_ended():
                executor.submit(
                    Helper.with_cleanup(self.run_reviewer),
                    patient_id,
                    note_id,
                    stop_and_go.created(),
                    stop_and_go.cycle(),
                )
                effects.append(Response(status_code=HTTPStatus.ACCEPTED))

        return effects

    def run_reviewer(self, patient_id: str, note_id: str, created: datetime, cycles: int) -> None:
        identification = IdentificationParameters(
            patient_uuid=patient_id,
            note_uuid=note_id,
            provider_uuid=str(Note.objects.get(id=note_id).provider.id),
            canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
        )
        settings = Settings.from_dictionary(self.secrets | {Constants.PROGRESS_SETTING_KEY: True})
        # end of the session
        Progress.send_to_user(identification, settings, "finished", Constants.PROGRESS_SECTION_EVENTS)

        if settings.audit_llm:
            log.info(f"  => final audit started...{note_id} / {cycles} cycles")
            credentials = AwsS3Credentials.from_dictionary(self.secrets)
            mapping = ImplementedCommands.schema_key2instruction()
            command2uuid = {
                LlmTurnsStore.indexed_instruction(mapping[command.schema_key], index): str(command.id)
                for index, command in enumerate(
                    Command.objects.filter(
                        patient__id=patient_id,
                        note__id=note_id,
                        state="staged",  # <--- TODO use an Enum when provided
                    ).order_by("dbid"),
                )
            }
            LlmDecisionsReviewer.review(identification, settings, credentials, command2uuid, created, cycles)
            log.info(f"  => final audit done ({note_id} / {cycles} cycles)")
        # end the flow
        progress = Constants.PROGRESS_END_OF_MESSAGES
        Progress.send_to_user(identification, settings, progress, Constants.PROGRESS_SECTION_EVENTS)

    def run_commander(self, patient_id: str, note_id: str, chunk_index: int) -> None:
        # add the running flag
        StopAndGo.get(note_id).set_cycle(chunk_index).set_running(True).save()
        try:
            identification = IdentificationParameters(
                patient_uuid=patient_id,
                note_uuid=note_id,
                provider_uuid=str(Note.objects.get(id=note_id).provider.id),
                canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
            )
            settings = Settings.from_dictionary(self.secrets | {Constants.PROGRESS_SETTING_KEY: True})
            aws_s3 = AwsS3Credentials.from_dictionary(self.secrets)
            audio_client = AudioClient.for_operation(
                self.secrets[Constants.SECRET_AUDIO_HOST],
                self.environment[Constants.CUSTOMER_IDENTIFIER],
                self.secrets[Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY],
            )

            MemoryLog.instance(identification, Constants.MEMORY_LOG_LABEL, aws_s3).output(
                f"SDK: {version} - "
                f"Text: {self.secrets[Constants.SECRET_TEXT_LLM_VENDOR]} - "
                f"Audio: {self.secrets[Constants.SECRET_AUDIO_LLM_VENDOR]}"
            )

            had_audio, effects = Commander.compute_audio(identification, settings, aws_s3, audio_client, chunk_index)

            # store the effects
            stop_and_go = StopAndGo.get(note_id)
            stop_and_go.add_paused_effects(effects).save()
            # messages
            if not (stop_and_go.is_ended() or stop_and_go.is_paused()):
                info = f"=> go to next iteration ({chunk_index + 1})"
                progress = f"waiting for the next cycle {chunk_index + 1}..."
                log.info(info)
                Progress.send_to_user(identification, settings, progress, Constants.PROGRESS_SECTION_EVENTS)
            # clean up and messages
            MemoryLog.end_session(note_id)
            LlmTurnsStore.end_session(note_id)

        finally:
            # remove the running flag
            StopAndGo.get(note_id).set_running(False).save()
