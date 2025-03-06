from argparse import ArgumentParser, ArgumentTypeError, Namespace
from datetime import datetime
from pathlib import Path
from sys import argv

from canvas_sdk.v1.data import Note, Patient

from hyperscribe.handlers.audio_interpreter import AudioInterpreter
from hyperscribe.handlers.commander import Commander
from hyperscribe.handlers.limited_cache import LimitedCache
from hyperscribe.handlers.memory_log import MemoryLog
from integrations.auditor_file import AuditorFile
from integrations.helper_settings import HelperSettings


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
        parser = ArgumentParser(description="Build all the files of the integration tests against a patient and the provided mp3 files")
        parser.add_argument("--patient", type=cls.validate_patient, required=True, help="Patient UUID")
        parser.add_argument("--label", type=str, required=True, help="Integration label")
        parser.add_argument("--mp3", nargs='+', type=cls.validate_files, required=True, help="List of MP3 files")
        return parser.parse_args()

    @classmethod
    def reset(cls) -> Namespace | None:
        if "--delete" in argv:
            parser = ArgumentParser()
            parser.add_argument("--delete", action="store_true")
            parser.add_argument("--label", type=str)
            return parser.parse_args()
        return None

    @classmethod
    def run(cls) -> None:
        # deletion of the integration files
        parameters = cls.reset()
        if parameters and parameters.delete:
            AuditorFile(parameters.label)
            print(f"Integration Label '{parameters.label}' deleted")
            return

        # creation of the integrations files
        parameters = cls.parameters()
        print(f"Patient UUID: {parameters.patient}")
        print(f"Integration Label: {parameters.label}")
        print("MP3 Files:")
        for file in parameters.mp3:
            print(f"- {file}")

        # auditor
        recorder = AuditorFile(parameters.label)
        # chatter
        note = Note.objects.filter(patient__id=parameters.patient).order_by("-dbid").first()  # the last note
        note_uuid = str(note.id)
        chatter = AudioInterpreter(
            HelperSettings.settings(),
            LimitedCache(parameters.patient, {}),
            parameters.patient,
            note_uuid,
            str(note.provider.id),
        )
        # audio
        audios: list[bytes] = []
        for file in parameters.mp3:
            with file.open("rb") as f:
                audios.append(f.read())

        MemoryLog.begin_session(note_uuid)
        Commander.audio2commands(recorder, audios, chatter, [])
        remote_path = f"{datetime.now().date().isoformat()}/case-builder-{parameters.label}.log"
        HelperSettings.flush_log(note_uuid, remote_path)


if __name__ == "__main__":
    CaseBuilder.run()
