import json
from argparse import ArgumentParser
from argparse import Namespace
from http import HTTPStatus
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory

import ffmpeg

from evaluations.auditor_file import AuditorFile
from evaluations.datastores.store_cases import StoreCases
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from evaluations.structures.evaluation_case import EvaluationCase
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.constants import Constants
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class BuilderDirectFromTuning:

    @classmethod
    def _parameters(cls, parser: ArgumentParser) -> None:
        raise NotImplementedError

    def _run(self) -> None:
        raise NotImplementedError

    @classmethod
    def parameters(cls) -> Namespace:
        parser = ArgumentParser(description="Build the case files directly from the tuning files stored in AWS S3")
        parser.add_argument("--patient", type=str, required=True, help="The patient UUID to consider")
        parser.add_argument("--note", type=str, required=True, help="The note UUID to consider")
        parser.add_argument("--path_temp_files", type=str, help="Folder to store temporary files, if provided, most existing files will be reused")
        parser.add_argument("--chunk_duration", type=int, required=True, help="Duration of each audio chunk in seconds")
        parser.add_argument("--force_refresh", action="store_true", help="Force refresh the temporary files")
        cls._parameters(parser)
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls.parameters()
        s3_credentials = HelperEvaluation.aws_s3_credentials()
        settings = HelperEvaluation.settings()
        identification = IdentificationParameters(
            patient_uuid=parameters.patient,
            note_uuid=parameters.note,
            provider_uuid=Constants.FAUX_PROVIDER_UUID,
            canvas_instance=HelperEvaluation.get_canvas_instance(),
        )
        with TemporaryDirectory() as temp_dir:
            if parameters.path_temp_files and (path := Path(parameters.path_temp_files)).exists():
                output_dir = path
            else:
                output_dir = Path(temp_dir)
            instance = cls(
                settings,
                s3_credentials,
                identification,
                output_dir,
                parameters.chunk_duration,
                parameters.force_refresh,
            )
            instance._run()

    def __init__(
            self,
            settings: Settings,
            s3_credentials: AwsS3Credentials,
            identification: IdentificationParameters,
            output_dir: Path,
            segment_duration_seconds: int,
            force_refresh: bool,
    ) -> None:
        self.settings = settings
        self.s3_credentials = s3_credentials
        self.identification = identification
        self.output_dir = output_dir
        self.segment_duration_seconds = segment_duration_seconds
        self.force_refresh = force_refresh

    def generate_case(
            self,
            limited_cache: LimitedCache,
            case_summary: CaseExchangeSummary,
            case_exchanges: list[CaseExchange],
    ) -> list[Instruction]:

        StoreCases.upsert(EvaluationCase(
            environment=self.identification.canvas_instance,
            patient_uuid=self.identification.patient_uuid,
            limited_cache=limited_cache.to_json(True),
            case_name=case_summary.title,
            # case_group=parameters.group,
            # case_type=parameters.type,
            cycles=len({line.chunk for line in case_exchanges}),
            description=case_summary.summary,
        ))
        chatter = AudioInterpreter(self.settings, self.s3_credentials, limited_cache, self.identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)
        cycle = 0
        for chunk, exchange in groupby(case_exchanges, key=lambda x: x.chunk):
            cycle += 1
            discussion.set_cycle(cycle)
            previous, _ = Commander.transcript2commands(
                AuditorFile(case_summary.title, cycle),
                [Line(speaker=line.speaker, text=line.text) for line in exchange],
                chatter,
                previous,
            )
        recorder = AuditorFile(case_summary.title, 0)
        recorder.generate_commands_summary()
        recorder.generate_html_summary()
        return recorder.summarized_generated_commands_as_instructions()

    def create_transcripts(self, mp3_files: list[Path], interpreter: AudioInterpreter) -> list[Path]:
        result: list[Path] = []
        last_exchange: list[Line] = []
        for chunk, mp3_file in enumerate(mp3_files):
            json_file = mp3_file.parent / f"transcript_{chunk:03d}.json"
            if self.force_refresh or not json_file.exists():
                with mp3_file.open("rb") as f:
                    audio_chunks = [f.read()]

                response = interpreter.combine_and_speaker_detection(audio_chunks, last_exchange)
                transcript = Line.load_from_json(response.content)
                with json_file.open("w") as f:
                    json.dump([line.to_json() for line in transcript], f, indent=2)

                last_exchange = Line.tail_of(transcript)

            result.append(json_file)
        return result

    def collated_webm_to_mp3(self) -> Path:
        client_s3 = AwsS3(self.s3_credentials)

        s3_folder = (f"hyperscribe-{self.identification.canvas_instance}/"
                     f"patient_{self.identification.patient_uuid}/"
                     f"note_{self.identification.note_uuid}")

        webm_file = self.output_dir / f"{s3_folder}/note_{self.identification.note_uuid}.webm"
        result = self.output_dir / f"{s3_folder}/note_{self.identification.note_uuid}.mp3"
        if self.force_refresh or webm_file.exists() is False:
            webm_file.unlink(missing_ok=True)

            for item in client_s3.list_s3_objects(s3_folder):
                # the limited_cache.json is assumed locally saved with all the webm files
                file = self.output_dir / item.key
                response = client_s3.access_s3_object(item.key)
                if response.status_code == HTTPStatus.OK.value:
                    file.parent.mkdir(parents=True, exist_ok=True)
                    with file.open("wb") as f:
                        f.write(response.content)

            with webm_file.open("wb") as f:
                for file in sorted(webm_file.parent.glob("*.webm"), key=lambda x: x.stem):
                    with file.open("rb") as f2:
                        f.write(f2.read())

        if self.force_refresh or result.exists() is False:
            (ffmpeg
             .input(webm_file.as_posix())
             .output(result.as_posix(), acodec='libmp3lame', ar=44100, ab='192k', vn=None)
             .overwrite_output()
             .run(overwrite_output=True, quiet=True))
        return result

    def split_audio(self, audio_file: Path) -> list[Path]:
        result: list[Path] = []
        audio_file_str = audio_file.as_posix()
        probe = ffmpeg.probe(audio_file_str)
        duration = float(probe['format']['duration'])
        chunk_index = 1
        chunk_time = 0.0

        while chunk_time < duration:
            end_time = min(chunk_time + self.segment_duration_seconds, duration)
            chunk_file = audio_file.parent / f"{audio_file.stem}_{self.segment_duration_seconds:03d}_{chunk_index:03d}.mp3"
            if self.force_refresh or chunk_file.exists() is False:
                (ffmpeg
                 .input(audio_file_str, ss=chunk_time, t=end_time - chunk_time)
                 .output(chunk_file.as_posix(), acodec='copy')
                 .overwrite_output()
                 .run(quiet=True))

            chunk_time = end_time
            chunk_index += 1
            result.append(chunk_file)
        return result
