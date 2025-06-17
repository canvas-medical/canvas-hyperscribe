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
        parser.add_argument('--combined', action='store_true', default=False, help="Combine the audio files into a single audio")
        parser.add_argument("--render", action="store_true", default=False, help="Upsert the commands of the last cycle to the patient's last note")
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorFile, identification: IdentificationParameters) -> None:
        settings = HelperEvaluation.settings()
        aws_s3_credentials = HelperEvaluation.aws_s3_credentials()
        limited_cache = cls._limited_cache_from(identification, settings)
        cycles = cls._combined_audios(parameters)

        StoreCases.upsert(EvaluationCase(
            environment=identification.canvas_instance,
            patient_uuid=parameters.patient,
            limited_cache=limited_cache.to_json(True),
            case_name=parameters.case,
            case_group=parameters.group,
            case_type=parameters.type,
            cycles=len(cycles),
            description=parameters.case,
        ))

        print(f"Patient UUID: {parameters.patient}")
        print(f"Evaluation Case: {parameters.case}")
        print("MP3 Files:")
        for file in parameters.mp3:
            print(f"- {file.name}")


        chatter = AudioInterpreter(settings, aws_s3_credentials, limited_cache, identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        transcript_tail = ""
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)
        for cycle, combined in enumerate(cycles):
            discussion.set_cycle(cycle + 1)
            previous, transcript_tail = cls._run_cycle(
                parameters.case,
                cycle,
                combined,
                chatter,
                previous,
                transcript_tail,
            )

        if parameters.render:
            cls._render_in_ui(parameters.case, identification, limited_cache)

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
