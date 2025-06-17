import json
from argparse import ArgumentParser, Namespace

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.constants import Constants
from evaluations.datastores.store_cases import StoreCases
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.identification_parameters import IdentificationParameters


class BuilderFromTuning(BuilderBase):

    @classmethod
    def _parameters(cls) -> Namespace:
        types = [Constants.TYPE_SITUATIONAL, Constants.TYPE_GENERAL]
        parser = ArgumentParser(description="Build the files of the evaluation tests against a patient based on the provided files")
        parser.add_argument("--case", type=str, required=True, help="Evaluation case")
        parser.add_argument("--group", type=str, help="Group of the case", default=Constants.GROUP_COMMON)
        parser.add_argument("--type", type=str, choices=types, help=f"Type of the case: {', '.join(types)}", default=types[1])
        parser.add_argument("--tuning-json", required=True, type=cls.validate_files, help="JSON file with the limited cache content")
        parser.add_argument("--tuning-mp3", required=True, nargs='+', type=cls.validate_files, help="MP3 files of the discussion")
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorFile, identification: IdentificationParameters) -> None:
        with parameters.tuning_json.open("r") as f:
            limited_cache_data = json.load(f)

        StoreCases.upsert(EvaluationCase(
            environment=identification.canvas_instance,
            patient_uuid=parameters.patient,
            limited_cache=limited_cache_data,
            case_name=parameters.case,
            case_group=parameters.group,
            case_type=parameters.type,
            cycles=len(parameters.tuning_mp3),
            description=parameters.case,
        ))

        print(f"Evaluation Case: {parameters.case}")
        print(f"JSON file: {parameters.tuning_json.name}")
        print("MP3 files:")
        for file in parameters.tuning_mp3:
            print(f"- {file.name}")

        limited_cache = LimitedCache.load_from_json(limited_cache_data)
        chatter = AudioInterpreter(
            HelperEvaluation.settings(),
            HelperEvaluation.aws_s3_credentials(),
            limited_cache,
            identification,
        )
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        audios: list[bytes] = []
        for file in parameters.tuning_mp3:
            with file.open("rb") as f:
                audios.append(f.read())

        transcript_tail = ""
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)
        for cycle in range(len(audios)):
            combined: list[bytes] = []
            for chunk in range(cycle, max(-1, cycle - (1 + Commander.MAX_PREVIOUS_AUDIOS)), -1):
                combined.insert(0, audios[chunk])

            discussion.set_cycle(cycle + 1)

            previous, transcript_tail = cls._run_cycle(
                parameters.case,
                cycle,
                combined,
                chatter,
                previous,
                transcript_tail,
            )
