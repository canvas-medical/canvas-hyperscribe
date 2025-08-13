from argparse import ArgumentTypeError
from argparse import Namespace
from datetime import datetime, UTC
from importlib import import_module
from pathlib import Path
from typing import Tuple

from canvas_sdk.v1.data import Patient, Command
from requests import post as requests_post, Response

from evaluations.auditors.auditor_store import AuditorStore
from evaluations.case_builders.builder_audit_url import BuilderAuditUrl
from evaluations.constants import Constants as EvaluationConstants
from evaluations.datastores.datastore_case import DatastoreCase
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.authenticator import Authenticator
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.constants import Constants as HyperscribeConstants
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.llm_decisions_reviewer import LlmDecisionsReviewer
from hyperscribe.libraries.memory_log import MemoryLog
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class BuilderBase:
    @classmethod
    def validate_files(cls, file_path: str) -> Path:
        file = Path(file_path)
        if not file.is_file():
            raise ArgumentTypeError(f"'{file_path}' is not a valid file")
        return file

    @classmethod
    def validate_patient(cls, patient_uuid: str) -> str:
        if not Patient.objects.filter(id=patient_uuid):
            raise ArgumentTypeError(f"'{patient_uuid}' is not a valid patient uuid")
        return patient_uuid

    @classmethod
    def _parameters(cls) -> Namespace:
        raise NotImplementedError

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorStore, identification: IdentificationParameters) -> None:
        raise NotImplementedError

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()
        if DatastoreCase.already_generated(parameters.case):
            print(f"Case '{parameters.case}' already generated")
            return

        if hasattr(parameters, "patient"):
            note_uuid = HelperEvaluation.get_note_uuid(parameters.patient)
            provider_uuid = HelperEvaluation.get_provider_uuid(parameters.patient)
        else:
            setattr(parameters, "patient", HyperscribeConstants.FAUX_PATIENT_UUID)
            note_uuid = HyperscribeConstants.FAUX_NOTE_UUID
            provider_uuid = HyperscribeConstants.FAUX_PROVIDER_UUID

        identification = IdentificationParameters(
            patient_uuid=parameters.patient,
            note_uuid=note_uuid,
            provider_uuid=provider_uuid,
            canvas_instance=HelperEvaluation.get_canvas_instance(),
        )

        _ = MemoryLog(identification, "case_builder")

        errors: dict = {}
        recorder = HelperEvaluation.get_auditor(parameters.case, 0)
        recorder.case_prepare()
        try:
            cls._run(parameters, recorder, identification)
        except Exception as e:
            errors = HelperEvaluation.trace_error(e)
        finally:
            recorder.case_finalize(errors)
        print(f"Summary can be viewed at: {recorder.generate_html_summary().as_uri()}")

        if (client_s3 := AwsS3(recorder.s3_credentials)) and client_s3.is_ready():
            remote_path = (
                f"hyperscribe-{identification.canvas_instance}/finals/"
                f"{datetime.now(UTC).date().isoformat()}/{parameters.case}.log"
            )
            client_s3.upload_text_to_s3(remote_path, MemoryLog.end_session(identification.note_uuid))
            print(f"Logs saved in: {remote_path}")

            if recorder.settings.audit_llm is True:
                discussion = CachedSdk.get_discussion(note_uuid)
                LlmDecisionsReviewer.review(
                    identification,
                    recorder.settings,
                    recorder.s3_credentials,
                    {},
                    discussion.created,
                    discussion.cycle,
                )
                BuilderAuditUrl.presigned_url(identification.patient_uuid, identification.note_uuid)

    @classmethod
    def _run_cycle(
        cls,
        auditor: AuditorStore,
        audios: list[bytes],
        chatter: AudioInterpreter,
        previous_instructions: list[Instruction],
        previous_transcript: list[Line],
    ) -> Tuple[list[Instruction], list[Line]]:
        if transcript := auditor.transcript():
            instructions, _ = Commander.transcript2commands(auditor, transcript, chatter, previous_instructions)
            end_of_transcript: list[Line] = []
        else:
            instructions, _, end_of_transcript = Commander.audio2commands(
                auditor,
                audios,
                chatter,
                previous_instructions,
                previous_transcript,
            )
        return instructions, end_of_transcript

    @classmethod
    def _limited_cache_from(cls, identification: IdentificationParameters, settings: Settings) -> LimitedCache:
        current_commands = Command.objects.filter(
            patient__id=identification.patient_uuid,
            note__id=identification.note_uuid,
            state="staged",  # <--- TODO use an Enum when provided
        ).order_by("dbid")

        return LimitedCache(
            identification.patient_uuid,
            identification.provider_uuid,
            Commander.existing_commands_to_coded_items(current_commands, settings.commands_policy, True),
        )

    @classmethod
    def _summary_generated_commands(cls, recorder: AuditorStore) -> list[dict]:
        result: dict[str, dict] = {}

        # common commands
        cycles = recorder.get_json(EvaluationConstants.PARAMETERS2COMMAND)
        for cycle, content in cycles.items():
            for instruction, command in zip(content["instructions"], content["commands"]):
                result[instruction["uuid"]] = {
                    "instruction": instruction["information"],
                    "command": cls._remove_uuids(command),
                }

        # questionnaires - command is from the last cycle
        cycles = recorder.get_json(EvaluationConstants.STAGED_QUESTIONNAIRES)
        if values := list(cycles.values()):
            for index, command in enumerate(values[-1]["commands"]):
                result[f"questionnaire_{index:02d}"] = {"instruction": "n/a", "command": cls._remove_uuids(command)}

        return list(result.values())

    @classmethod
    def _remove_uuids(cls, command: dict) -> dict:
        return {
            "module": command["module"],
            "class": command["class"],
            "attributes": {
                key: value for key, value in command["attributes"].items() if key not in ("note_uuid", "command_uuid")
            },
        }

    @classmethod
    def _render_in_ui(
        cls,
        recorder: AuditorStore,
        identification: IdentificationParameters,
        limited_cache: LimitedCache,
    ) -> None:
        result: list[dict] = []
        commands = [summary["command"] for summary in cls._summary_generated_commands(recorder)]
        if not commands:
            return

        # define the note and command uuids
        mapping = ImplementedCommands.schema_key2instruction()
        initials = limited_cache.staged_commands_as_instructions(mapping)
        consumed_indexes: list[int] = []
        for command in commands:
            # retrieve the current command, if any
            module_name = command["module"]
            class_name = command["class"]
            module_itself = import_module(module_name)
            class_itself = getattr(module_itself, class_name)
            # assert issubclass(class_itself, BaseCommand)
            for idx, initial in enumerate(initials):
                if initial.instruction == mapping[class_itself.Meta.key] and idx not in consumed_indexes:
                    command_uuid = initial.uuid
                    consumed_indexes.append(idx)
                    break
            else:
                command_uuid = None

            # set the command uuid
            command["attributes"]["command_uuid"] = command_uuid
            # set the note uuid
            command["attributes"]["note_uuid"] = identification.note_uuid
            result.append(command)

        cls._post_commands(result)

    @classmethod
    def _post_commands(cls, commands: list[dict]) -> Response:
        url = Authenticator.presigned_url(
            HelperEvaluation.settings().api_signing_key,
            f"{HelperEvaluation.get_canvas_host()}{HyperscribeConstants.PLUGIN_API_BASE_ROUTE}/case_builder",
            {},
        )
        return requests_post(
            url,
            headers={"Content-Type": "application/json"},
            json=commands,
            verify=True,
            timeout=None,
        )
