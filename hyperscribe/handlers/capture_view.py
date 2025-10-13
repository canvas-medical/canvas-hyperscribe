import re
from datetime import datetime, UTC
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
from requests import post as requests_post

from hyperscribe.handlers.progress import Progress
from hyperscribe.libraries.audio_client import AudioClient
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.limited_cache_loader import LimitedCacheLoader
from hyperscribe.libraries.llm_decisions_reviewer import LlmDecisionsReviewer
from hyperscribe.libraries.llm_turns_store import LlmTurnsStore
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.libraries.stop_and_go import StopAndGo
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.notion_feedback_record import NotionFeedbackRecord
from hyperscribe.structures.progress_message import ProgressMessage
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

    def trigger_render(self, patient_id: str, note_id: str) -> Response:
        url = Authenticator.presigned_url(
            Settings.from_dictionary(self.secrets).api_signing_key,
            f"{Helper.canvas_host(self.environment[Constants.CUSTOMER_IDENTIFIER])}"
            f"{Constants.PLUGIN_API_BASE_ROUTE}/render/{patient_id}/{note_id}",
            {},
        )
        return requests_post(
            url,
            headers={"Content-Type": "application/json"},
            verify=True,
            timeout=None,
        )

    def session_progress_log(self, patient_id: str, note_id: str, progress: str) -> None:
        identification = IdentificationParameters(
            patient_uuid=patient_id,
            note_uuid=note_id,
            provider_uuid="",
            canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
        )
        settings = Settings.from_dictionary(self.secrets | {Constants.PROGRESS_SETTING_KEY: True})
        messages = [ProgressMessage(message=progress, section=Constants.PROGRESS_SECTION_EVENTS)]
        Progress.send_to_user(identification, settings, messages)

    @api.get("/capture/<patient_id>/<note_id>/<note_reference>")
    def capture_get(self) -> list[Response | Effect]:
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]
        note_reference = self.request.path_params["note_reference"]

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
        ws_progress_url = (
            f"{Helper.canvas_ws_host(self.environment[Constants.CUSTOMER_IDENTIFIER])}"
            f"{Constants.PLUGIN_WS_BASE_ROUTE}/{Constants.WS_CHANNEL_PROGRESSES}/"
        )

        stop_and_go = StopAndGo.get(note_id)
        context = {
            "patientUuid": patient_id,
            "noteUuid": note_id,
            "noteReference": note_reference,
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
            executor.submit(Helper.with_cleanup(self.trigger_render), patient_id, note_id)

        return [Response(b"Audio chunk saved OK", HTTPStatus.CREATED)]

    @api.post("/render/<patient_id>/<note_id>")
    def render_effect_post(self) -> list[Response | Effect]:
        patient_id = self.request.path_params["patient_id"]
        note_id = self.request.path_params["note_id"]

        effects: list[Response | Effect] = []
        stop_and_go = StopAndGo.get(note_id)
        if paused := stop_and_go.paused_effects():
            effects.extend(paused)
            stop_and_go.reset_paused_effect().set_delay().save()
            executor.submit(Helper.with_cleanup(self.trigger_render), patient_id, note_id)  # <-- loop!
        elif not stop_and_go.is_running():
            stop_and_go.consume_delay()
            identification = IdentificationParameters(
                patient_uuid=patient_id,
                note_uuid=note_id,
                provider_uuid=str(Note.objects.get(id=note_id).provider.id),
                canvas_instance=self.environment[Constants.CUSTOMER_IDENTIFIER],
            )
            if stop_and_go.consume_next_waiting_cycles(True):
                settings = Settings.from_dictionary(self.secrets)
                cache_loader = LimitedCacheLoader(identification, settings.commands_policy, False)
                executor.submit(
                    Helper.with_cleanup(self.run_commander),
                    identification,
                    cache_loader.load_from_database(),
                    stop_and_go.cycle(),
                )
            elif stop_and_go.is_ended():
                executor.submit(
                    Helper.with_cleanup(self.run_reviewer),
                    identification,
                    stop_and_go.created(),
                    stop_and_go.cycle(),
                )

        return effects

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
        # end of the session
        messages = [
            ProgressMessage(
                message="finished",
                section=Constants.PROGRESS_SECTION_EVENTS,
            )
        ]
        Progress.send_to_user(identification, settings, messages)

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
        messages = [
            ProgressMessage(
                message=Constants.PROGRESS_END_OF_MESSAGES,
                section=Constants.PROGRESS_SECTION_EVENTS,
            )
        ]
        Progress.send_to_user(identification, settings, messages)

    def run_commander(
        self,
        identification: IdentificationParameters,
        cache: LimitedCache,
        chunk_index: int,
    ) -> None:
        # add the running flag
        StopAndGo.get(identification.note_uuid).set_cycle(chunk_index).set_running(True).save()
        try:
            settings = Settings.from_dictionary(self.secrets | {Constants.PROGRESS_SETTING_KEY: True})
            aws_s3 = AwsS3Credentials.from_dictionary(self.secrets)
            audio_client = AudioClient.for_operation(
                self.secrets[Constants.SECRET_AUDIO_HOST],
                self.environment[Constants.CUSTOMER_IDENTIFIER],
                self.secrets[Constants.SECRET_AUDIO_HOST_PRE_SHARED_KEY],
            )

            MemoryLog.instance(identification, Constants.MEMORY_LOG_LABEL, aws_s3).output(
                f"SDK: {version} - "
                f"Text: {settings.llm_text.vendor} - "
                f"Audio: {settings.llm_audio.vendor} - "
                f"Workers: {settings.max_workers}"
            )

            had_audio, effects = Commander.compute_audio(
                identification,
                settings,
                aws_s3,
                audio_client,
                cache,
                chunk_index,
            )

            # store the effects
            stop_and_go = StopAndGo.get(identification.note_uuid)
            stop_and_go.add_paused_effects(effects).save()
            # messages
            if stop_and_go.waiting_cycles() or not stop_and_go.is_ended():
                log.info(f"=> go to next iteration ({chunk_index + 1})")
                messages = [
                    ProgressMessage(
                        message=f"waiting for the next cycle {chunk_index + 1}...",
                        section=Constants.PROGRESS_SECTION_TECHNICAL,
                    )
                ]
                Progress.send_to_user(identification, settings, messages)
            # clean up and messages
            MemoryLog.end_session(identification.note_uuid)
            LlmTurnsStore.end_session(identification.note_uuid)
        except Exception as e:
            log.info("************************")
            log.info(f"Error while running commander: {e}")
            log.info("************************")
        finally:
            # remove the running flag
            StopAndGo.get(identification.note_uuid).set_running(False).save()
            self.trigger_render(identification.patient_uuid, identification.note_uuid)
