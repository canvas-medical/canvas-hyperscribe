import json
from argparse import ArgumentParser, Namespace
from pathlib import Path
from evaluations.auditors.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.constants import Constants
from evaluations.datastores.sqllite.store_cases import StoreCases
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
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
    def _run(cls, parameters: Namespace, recorder: AuditorFile, identification: IdentificationParameters) -> None:
        with parameters.chart.open("r") as f:
            chart_data = json.load(f)
        limited_cache = LimitedCache.load_from_json(chart_data)

        with parameters.transcript.open("r") as f:
            transcript_data = json.load(f)
        transcript = Line.load_from_json(transcript_data)

        StoreCases.upsert(EvaluationCase(
            environment=identification.canvas_instance,
            patient_uuid=identification.patient_uuid,
            limited_cache=chart_data,
            case_name=parameters.case,
            case_group=parameters.group,
            case_type=parameters.type,
            cycles=max(1, parameters.cycles),
            description=parameters.case,
        ))

        chatter = AudioInterpreter(
            HelperEvaluation.settings(),
            HelperEvaluation.aws_s3_credentials(),
            limited_cache,
            identification
        )

        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(identification.note_uuid)

        if parameters.cycles < 2:
            discussion.set_cycle(1)
            Commander.transcript2commands(recorder, transcript, chatter, previous)
        else:
            length, extra = divmod(len(transcript), parameters.cycles)
            length += 1 if extra else 0
            for cycle in range(parameters.cycles):
                start = cycle * length
                discussion.set_cycle(cycle + 1)
                prev, _ = Commander.transcript2commands(
                    AuditorFile(parameters.case, cycle),
                    transcript[start:start + length],
                    chatter,
                    previous
                )
                previous = prev

        if parameters.render:
            cls._render_in_ui(parameters.case, identification, limited_cache)
