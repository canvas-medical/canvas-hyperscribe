import json
from argparse import ArgumentParser, Namespace

from evaluations.auditors.auditor_store import AuditorStore
from evaluations.case_builders.builder_base import BuilderBase
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


class BuilderFromTuning(BuilderBase):
    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(
            description="Build the files of the evaluation tests against a patient based on the provided files",
        )
        parser.add_argument("--case", type=str, required=True, help="Evaluation case")
        parser.add_argument(
            "--tuning-json",
            required=True,
            type=cls.validate_files,
            help="JSON file with the limited cache content",
        )
        parser.add_argument(
            "--tuning-mp3",
            required=True,
            nargs="+",
            type=cls.validate_files,
            help="MP3 files of the discussion",
        )
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorStore, identification: IdentificationParameters) -> None:
        with parameters.tuning_json.open("r") as f:
            limited_cache_data = json.load(f)

        print(f"Evaluation Case: {parameters.case}")
        print(f"JSON file: {parameters.tuning_json.name}")
        print("MP3 files:")
        for file in parameters.tuning_mp3:
            print(f"- {file.name}")

        limited_cache = LimitedCache.load_from_json(limited_cache_data)
        audios: list[bytes] = []
        for file in parameters.tuning_mp3:
            with file.open("rb") as f:
                audios.append(f.read())

        #recorder.case_update_limited_cache(limited_cache.to_json(True))

        chatter = AudioInterpreter(recorder.settings, recorder.s3_credentials, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)

        transcript_tail: list[Line] = []
        for cycle in range(len(audios)):
            combined: list[bytes] = []
            for chunk in range(cycle, max(-1, cycle - (1 + Commander.MAX_PREVIOUS_AUDIOS)), -1):
                combined.insert(0, audios[chunk])

            discussion.set_cycle(cycle + 1)
            recorder.set_cycle(cycle + 1)

            previous, transcript_tail = cls._run_cycle(recorder, combined, chatter, previous, transcript_tail)
