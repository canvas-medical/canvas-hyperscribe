import json
from argparse import ArgumentParser, Namespace

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.constants import Constants
from evaluations.datastores.store_cases import StoreCases
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.audio_interpreter import AudioInterpreter
from hyperscribe.handlers.commander import Commander
from hyperscribe.handlers.limited_cache import LimitedCache
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
        parser.add_argument("--tuning-mp3", required=True, type=cls.validate_files, help="MP3 file of the discussion")
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorFile, identification: IdentificationParameters) -> None:
        with parameters.tuning_json.open("r") as f:
            limited_cache = json.load(f)

        StoreCases.upsert(EvaluationCase(
            environment=identification.canvas_instance,
            patient_uuid=parameters.patient,
            limited_cache=limited_cache,
            case_name=parameters.case,
            case_group=parameters.group,
            case_type=parameters.type,
            description=parameters.case,
        ))

        print(f"Evaluation Case: {parameters.case}")
        print(f"JSON file: {parameters.tuning_json.name}")
        print(f"MP3 file: {parameters.tuning_mp3.name}")

        chatter = AudioInterpreter(
            HelperEvaluation.settings(),
            HelperEvaluation.aws_s3_credentials(),
            LimitedCache.load_from_json(limited_cache),
            identification,
        )

        audios: list[bytes] = []
        with parameters.tuning_mp3.open("rb") as f:
            audios.append(f.read())
        Commander.audio2commands(recorder, audios, chatter, [])
