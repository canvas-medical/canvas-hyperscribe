import json
from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from os import environ
from pathlib import Path
from sys import argv

from canvas_sdk.v1.data import Note, Patient

from evaluations.auditor_file import AuditorFile
from evaluations.constants import Constants
from evaluations.datastores.store_cases import StoreCases
from evaluations.helper_settings import HelperSettings
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.audio_interpreter import AudioInterpreter
from hyperscribe.handlers.aws_s3 import AwsS3
from hyperscribe.handlers.commander import Commander
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.memory_log import MemoryLog
from hyperscribe.handlers.structures.line import Line


class CaseBuilder:

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
    def parameters(cls) -> Namespace:
        types = [Constants.TYPE_SITUATIONAL, Constants.TYPE_GENERAL]
        parser = ArgumentParser(description="Build the files of the evaluation tests against a patient based on the provided files")
        parser.add_argument("--patient", type=cls.validate_patient, required=True, help="Patient UUID")
        parser.add_argument("--case", type=str, required=True, help="Evaluation case")
        parser.add_argument("--group", type=str, help="Group of the case", default=Constants.GROUP_COMMON)
        parser.add_argument("--type", type=str, choices=types, help=f"Type of the case: {', '.join(types)}", default=types[1])
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--mp3", nargs='+', type=cls.validate_files, help="List of MP3 files")
        group.add_argument("--transcript", type=cls.validate_files, help="JSON file with transcript")
        return parser.parse_args()

    @classmethod
    def reset(cls) -> Namespace | None:
        if "--delete" in argv:
            parser = ArgumentParser()
            parser.add_argument("--delete", action="store_true")
            parser.add_argument("--case", type=str)
            return parser.parse_args()
        return None

    @classmethod
    def run(cls) -> None:
        # deletion of the evaluation files
        parameters = cls.reset()
        if parameters and parameters.delete:
            AuditorFile(parameters.case)
            StoreCases.delete(parameters.case)
            print(f"Evaluation Case '{parameters.case}' deleted (files and record)")
            return

        # creation of the evaluations files
        parameters = cls.parameters()
        StoreCases.upsert(EvaluationCase(
            environment=environ.get(Constants.CANVAS_SDK_DB_HOST),
            patient_uuid=parameters.patient,
            case_name=parameters.case,
            case_group=parameters.group,
            case_type=parameters.type,
            description=parameters.case,
        ))
        print(f"Patient UUID: {parameters.patient}")
        print(f"Evaluation Case: {parameters.case}")
        if parameters.mp3:
            print("MP3 Files:")
            for file in parameters.mp3:
                print(f"- {file}")
        if parameters.transcript:
            print(f"JSON file: {parameters.transcript}")

        # auditor
        recorder = AuditorFile(parameters.case)
        # chatter
        note = Note.objects.filter(patient__id=parameters.patient).order_by("-dbid").first()  # the last note
        note_uuid = str(note.id)
        chatter = AudioInterpreter(
            HelperSettings.settings(),
            HelperSettings.aws_s3_credentials(),
            LimitedCache(parameters.patient, {}),
            parameters.patient,
            note_uuid,
            str(note.provider.id),
        )
        MemoryLog.begin_session(note_uuid)
        # audio
        if parameters.mp3:
            audios: list[bytes] = []
            for file in parameters.mp3:
                with file.open("rb") as f:
                    audios.append(f.read())
            Commander.audio2commands(recorder, audios, chatter, [])
        # json
        if parameters.transcript:
            with parameters.transcript.open("r") as f:
                transcript = Line.load_from_json(json.load(f))
            Commander.transcript2commands(recorder, transcript, chatter, [])

        if (client_s3 := AwsS3(HelperSettings.aws_s3_credentials())) and client_s3.is_ready():
            remote_path = f"{datetime.now().date().isoformat()}/case-builder-{parameters.case}.log"
            client_s3.upload_text_to_s3(remote_path, MemoryLog.end_session(note_uuid))
            print(f"Logs saved in: {remote_path}")


if __name__ == "__main__":
    CaseBuilder.run()
