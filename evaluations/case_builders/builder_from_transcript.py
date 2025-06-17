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
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line


class BuilderFromTranscript(BuilderBase):

    @classmethod
    def _parameters(cls) -> Namespace:
        types = [Constants.TYPE_SITUATIONAL, Constants.TYPE_GENERAL]
        parser = ArgumentParser(description="Build the files of the evaluation tests against a patient based on the provided files")
        parser.add_argument("--patient", type=cls.validate_patient, required=True, help="Patient UUID")
        parser.add_argument("--case", type=str, required=True, help="Evaluation case")
        parser.add_argument("--group", type=str, help="Group of the case", default=Constants.GROUP_COMMON)
        parser.add_argument("--type", type=str, choices=types, help=f"Type of the case: {', '.join(types)}", default=types[1])
        parser.add_argument("--transcript", type=cls.validate_files, help="JSON file with transcript")
        parser.add_argument("--cycles", type=int, help="Split the transcript in as many cycles", default=1)
        parser.add_argument("--render", action="store_true", default=False, help="Upsert the commands of the last cycle to the patient's last note")
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorFile, identification: IdentificationParameters) -> None:
        settings = HelperEvaluation.settings()
        aws_s3_credentials = HelperEvaluation.aws_s3_credentials()
        limited_cache = cls._limited_cache_from(identification, settings)

        StoreCases.upsert(EvaluationCase(
            environment=identification.canvas_instance,
            patient_uuid=parameters.patient,
            limited_cache=limited_cache.to_json(True),
            case_name=parameters.case,
            case_group=parameters.group,
            case_type=parameters.type,
            cycles=max(1, parameters.cycles),
            description=parameters.case,
        ))

        print(f"Patient UUID: {parameters.patient}")
        print(f"Evaluation Case: {parameters.case}")
        print(f"JSON file: {parameters.transcript.name}")
        print(f"Cycles: {parameters.cycles}")

        chatter = AudioInterpreter(settings, aws_s3_credentials, limited_cache, identification)

        with parameters.transcript.open("r") as f:
            transcript = Line.load_from_json(json.load(f))

        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())

        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)
        if parameters.cycles < 2:
            discussion.set_cycle(1)
            Commander.transcript2commands(recorder, transcript, chatter, previous)
        else:
            length, extra = divmod(len(transcript), parameters.cycles)
            length += (1 if extra else 0)
            for cycle in range(0, parameters.cycles):
                idx = cycle * length
                discussion.set_cycle(cycle + 1)
                previous, _ = Commander.transcript2commands(
                    AuditorFile(parameters.case, cycle),
                    transcript[idx:idx + length],
                    chatter,
                    previous,
                )
        if parameters.render:
            cls._render_in_ui(parameters.case, identification, limited_cache)
