from argparse import ArgumentParser, Namespace

from evaluations.auditors.auditor_store import AuditorStore
from evaluations.case_builders.builder_base import BuilderBase
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


class BuilderFromMp3(BuilderBase):
    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(
            description="Build the files of the evaluation tests against a patient based on the provided files",
        )
        parser.add_argument("--patient", type=cls.validate_patient, required=True, help="Patient UUID")
        parser.add_argument("--case", type=str, required=True, help="Evaluation case")
        parser.add_argument("--mp3", required=True, nargs="+", type=cls.validate_files, help="List of MP3 files")
        parser.add_argument(
            "--combined",
            action="store_true",
            default=False,
            help="Combine the audio files into a single audio",
        )
        parser.add_argument(
            "--render",
            action="store_true",
            default=False,
            help="Upsert the commands of the last cycle to the patient's last note",
        )
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorStore, identification: IdentificationParameters) -> None:
        limited_cache = cls._limited_cache_from(identification, recorder.settings)
        cycles = cls._combined_audios(parameters)

        print(f"Patient UUID: {parameters.patient}")
        print(f"Evaluation Case: {parameters.case}")
        print("MP3 Files:")
        for file in parameters.mp3:
            print(f"- {file.name}")

        recorder.case_update_limited_cache(limited_cache.to_json(True))

        chatter = AudioInterpreter(recorder.settings, recorder.s3_credentials, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)

        transcript_tail: list[Line] = []
        for cycle, combined in enumerate(cycles):
            discussion.set_cycle(cycle + 1)
            recorder.set_cycle(cycle + 1)

            previous, transcript_tail = cls._run_cycle(recorder, combined, chatter, previous, transcript_tail)

        if parameters.render:
            cls._render_in_ui(recorder, identification, limited_cache)

    @classmethod
    def _combined_audios(cls, parameters: Namespace) -> list[list[bytes]]:
        audios: list[bytes] = []
        for file in parameters.mp3:
            with file.open("rb") as f:
                audios.append(f.read())

        cycles: list[list[bytes]] = []
        if parameters.combined:
            cycles.append(audios)
        else:
            for cycle in range(len(audios)):
                cycles.append([])
                for chunk in range(cycle, max(-1, cycle - (1 + Commander.MAX_PREVIOUS_AUDIOS)), -1):
                    cycles[-1].insert(0, audios[chunk])
        return cycles
