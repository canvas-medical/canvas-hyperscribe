import json
from argparse import ArgumentParser, Namespace

from evaluations.auditors.auditor_store import AuditorStore
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.constants import Constants
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.commander import Commander
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


class BuilderFromChartTranscript(BuilderBase):
    @classmethod
    def _parameters(cls) -> Namespace:
        types = [Constants.TYPE_SITUATIONAL, Constants.TYPE_GENERAL]
        parser = ArgumentParser(description="Generate commands summary from chart + transcript")
        parser.add_argument("--case", type=str, required=True, help="Evaluation case name (used as directory)")
        parser.add_argument("--chart", type=cls.validate_files, required=True, help="Path to limited_cache JSON file")
        parser.add_argument("--transcript", type=cls.validate_files, required=True, help="Path to transcript JSON file")
        parser.add_argument("--group", type=str, default=Constants.GROUP_COMMON, help="Group of the case")
        parser.add_argument("--type", type=str, choices=types, default=types[1], help="Type of the case")
        parser.add_argument("--cycles", type=int, default=1, help="Number of transcript cycles")
        parser.add_argument("--render", action="store_true", help="Render commands to UI")
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorStore, identification: IdentificationParameters) -> None:
        with parameters.chart.open("r") as f:
            chart_data = json.load(f)
        limited_cache = LimitedCache.load_from_json(chart_data)

        with parameters.transcript.open("r") as f:
            transcript = Line.load_from_json(json.load(f))
        cycles = min(max(1, parameters.cycles), len(transcript))

        print(f"Evaluation Case: {parameters.case}")
        print(f"Chart file: {parameters.chart.name}")
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
