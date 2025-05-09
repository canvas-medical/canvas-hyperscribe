from argparse import ArgumentParser, Namespace

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_base import BuilderBase
from evaluations.constants import Constants
from evaluations.datastores.store_cases import StoreCases
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_discussion import CachedDiscussion
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction


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
        return parser.parse_args()

    @classmethod
    def _run(cls, parameters: Namespace, recorder: AuditorFile, identification: IdentificationParameters) -> None:
        limited_cache = cls._limited_cache_from(identification)

        StoreCases.upsert(EvaluationCase(
            environment=identification.canvas_instance,
            patient_uuid=parameters.patient,
            limited_cache=limited_cache.to_json(True),
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

        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        if parameters.combined or (len(parameters.mp3) == 1):
            cls._run_combined(recorder, chatter, audios, previous)
        else:
            cls._run_chunked(parameters, chatter, audios, previous)

    @classmethod
    def _run_combined(cls, recorder: AuditorFile, chatter: AudioInterpreter, audios: list[bytes], previous: list[Instruction]) -> None:
        CachedDiscussion.get_discussion(chatter.identification.note_uuid).add_one()
        Commander.audio2commands(recorder, audios, chatter, previous, "")

    @classmethod
    def _run_chunked(cls, parameters: Namespace, chatter: AudioInterpreter, audios: list[bytes], previous: list[Instruction]) -> None:
        transcript_tail = ""
        discussion = CachedDiscussion.get_discussion(chatter.identification.note_uuid)
        for cycle in range(len(audios)):
            combined: list[bytes] = []
            for chunk in range(cycle, max(-1, cycle - Commander.MAX_PREVIOUS_AUDIOS), -1):
                combined.insert(0, audios[chunk])

            discussion.add_one()
            recorder = AuditorFile(f"{parameters.case}{Constants.CASE_CYCLE_SUFFIX}{cycle:02d}")
            previous, _, transcript_tail = Commander.audio2commands(recorder, combined, chatter, previous, transcript_tail)
