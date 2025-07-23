import json
from argparse import ArgumentParser, Namespace

from evaluations.auditors.auditor_store import AuditorStore
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.constants import Constants
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


class BuilderFromTranscript(BuilderBase):
    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(
            description="Build the files of the evaluation tests against a patient based on the provided files",
        )
        parser.add_argument("--patient", type=cls.validate_patient, required=True, help="Patient UUID")
        parser.add_argument("--case", type=str, required=True, help="Evaluation case")
        parser.add_argument("--transcript", type=cls.validate_files, help="JSON file with transcript")
        parser.add_argument("--cycles", type=int, help="Split the transcript in as many cycles", default=1)
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

        with parameters.transcript.open("r") as f:
            transcript = Line.load_from_json(json.load(f))
        cycles = min(max(1, parameters.cycles), len(transcript))

        print(f"Patient UUID: {parameters.patient}")
        print(f"Evaluation Case: {parameters.case}")
        print(f"JSON file: {parameters.transcript.name}")
        print(f"Cycles: {cycles}")

        recorder.case_update_limited_cache(limited_cache.to_json(True))

        chatter = AudioInterpreter(recorder.settings, recorder.s3_credentials, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)

        length, extra = divmod(len(transcript), cycles)
        length += 1 if extra else 0

        for cycle in range(cycles):
            idx = cycle * length
            cycle += 1
            discussion.set_cycle(cycle)
            recorder.set_cycle(cycle)
            recorder.upsert_json(
                Constants.AUDIO2TRANSCRIPT,
                {recorder.cycle_key: [line.to_json() for line in transcript[idx : idx + length]]},
            )
            previous, _ = Commander.transcript2commands(recorder, transcript[idx : idx + length], chatter, previous)

        if parameters.render:
            cls._render_in_ui(recorder, identification, limited_cache)
