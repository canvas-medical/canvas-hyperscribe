from argparse import ArgumentParser, Namespace

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.constants import Constants
from evaluations.datastores.store_cases import StoreCases
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.audio_interpreter import AudioInterpreter
from hyperscribe.handlers.commander import Commander
from hyperscribe.structures.identification_parameters import IdentificationParameters


class BuilderFromMp3(BuilderBase):

    @classmethod
    def _parameters(cls) -> Namespace:
        types = [Constants.TYPE_SITUATIONAL, Constants.TYPE_GENERAL]
        parser = ArgumentParser(description="Build the files of the evaluation tests against a patient based on the provided files")
        parser.add_argument("--patient", type=cls.validate_patient, required=True, help="Patient UUID")
        parser.add_argument("--case", type=str, required=True, help="Evaluation case")
        parser.add_argument("--group", type=str, help="Group of the case", default=Constants.GROUP_COMMON)
        parser.add_argument("--type", type=str, choices=types, help=f"Type of the case: {', '.join(types)}", default=types[1])
        parser.add_argument("--mp3", required=True, nargs='+', type=cls.validate_files, help="List of MP3 files")
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorFile, identification: IdentificationParameters) -> None:
        limited_cache = cls._limited_cache_from(identification)

        StoreCases.upsert(EvaluationCase(
            environment=identification.canvas_instance,
            patient_uuid=parameters.patient,
            limited_cache=limited_cache.to_json(),
            case_name=parameters.case,
            case_group=parameters.group,
            case_type=parameters.type,
            description=parameters.case,
        ))

        print(f"Patient UUID: {parameters.patient}")
        print(f"Evaluation Case: {parameters.case}")
        print("MP3 Files:")
        for file in parameters.mp3:
            print(f"- {file.name}")

        chatter = AudioInterpreter(
            HelperEvaluation.settings(),
            HelperEvaluation.aws_s3_credentials(),
            limited_cache,
            identification,
        )

        audios: list[bytes] = []
        for file in parameters.mp3:
            with file.open("rb") as f:
                audios.append(f.read())
        Commander.audio2commands(recorder, audios, chatter, [])
