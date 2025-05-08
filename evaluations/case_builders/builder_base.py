from argparse import ArgumentTypeError, Namespace
from datetime import datetime
from pathlib import Path

from canvas_sdk.v1.data import Patient, Command

from evaluations.auditor_file import AuditorFile
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.handlers.aws_s3 import AwsS3
from hyperscribe.handlers.commander import Commander
from hyperscribe.handlers.constants import Constants as HyperscribeConstants
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.llm_decisions_reviewer import LlmDecisionsReviewer
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.structures.identification_parameters import IdentificationParameters


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
    def _run(cls, parameters: Namespace, recorder: AuditorFile, identification: IdentificationParameters) -> None:
        raise NotImplementedError

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()
        # auditor
        recorder = AuditorFile(parameters.case)
        if not recorder.is_ready():
            print(f"Case '{parameters.case}': some files exist already")
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

        memory_log = MemoryLog(identification, "case_builder")

        cls._run(parameters, recorder, identification)

        aws_s3_credentials = HelperEvaluation.aws_s3_credentials()
        if (client_s3 := AwsS3(aws_s3_credentials)) and client_s3.is_ready():
            remote_path = f"{identification.canvas_instance}/finals/{datetime.now().date().isoformat()}/{parameters.case}.log"
            client_s3.upload_text_to_s3(remote_path, MemoryLog.end_session(identification.note_uuid))
            print(f"Logs saved in: {remote_path}")

        LlmDecisionsReviewer.review(
            identification,
            HelperEvaluation.settings(),
            aws_s3_credentials,
            memory_log,
            {},
        )

    @classmethod
    def _limited_cache_from(cls, identification: IdentificationParameters) -> LimitedCache:
        current_commands = Command.objects.filter(
            patient__id=identification.patient_uuid,
            note__id=identification.note_uuid,
            state="staged",  # <--- TODO use an Enum when provided
        ).order_by("dbid")

        return LimitedCache(
            identification.patient_uuid,
            Commander.existing_commands_to_coded_items(current_commands),
        )
