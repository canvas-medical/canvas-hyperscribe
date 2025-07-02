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
from hyperscribe.libraries.helper import Helper
from hyperscribe.libraries.implemented_commands import ImplementedCommands
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.libraries.memory_log import MemoryLog
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
                AuditorFile.default_instance(case_summary.title, cycle),
                [Line(speaker=line.speaker, text=line.text) for line in exchange],
                chatter,
                previous,
            )
        recorder = AuditorFile.default_instance(case_summary.title, 0)
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

    def anonymize_transcripts(self, transcript_files: list[Path]) -> list[Path]:
        result: list[Path] = []
        memory_log = MemoryLog.instance(self.identification, "anonymize_transcript", self.s3_credentials)
        schema_anonymization = self.schema_anonymization()
        schema_changes = self.schema_changes()

        used_anonymizations: dict = {}
        for chunk, transcript in enumerate(transcript_files):
            anonymized = transcript.parent / f"transcript_anonymized_{chunk:03d}.json"
            result.append(anonymized)
            if anonymized.exists() and not self.force_refresh:
                continue

            chatter = Helper.chatter(self.settings, memory_log)
            chatter.set_system_prompt([
                "You are a medical transcript anonymization specialist with expertise in healthcare privacy compliance."
                "",
                "Your task is to remove all personally identifiable information (PII) from medical transcripts while preserving "
                "complete clinical context and medical accuracy through realistic replacements.",
                "",
                "**Anonymization Approach**",
                "Use realistic, plausible substitutions rather than placeholders:",
                "- Replace names with culturally appropriate alternatives of similar length/structure",
                "- Substitute locations with comparable geographic areas (similar urban/rural, climate, healthcare infrastructure)",
                "- Change dates while maintaining temporal relationships and seasonal context when medically relevant",
                "- Replace specific institutions with similar types (community hospital → regional medical center)",
                "",
                "**Medical Preservation Requirements**",
                "- Maintain ALL clinical terminology, symptoms, diagnoses, differential diagnoses",
                "- Preserve exact medication names, dosages, frequencies, routes of administration",
                "- Keep all vital signs, laboratory values, imaging results, and measurements unchanged",
                "- Retain medical history details, surgical history, family medical history",
                "- Preserve healthcare provider specialties and their clinical roles",
                "- Maintain treatment timelines and follow-up schedules precisely",
                "- Keep allergies, adverse reactions, and contraindications intact",
                "",
                "Format the anonymized transcript following the JSON Schema:",
                "```json",
                json.dumps(schema_anonymization, indent=1),
                "```",
                "",
                "**Global Consistency**: Use identical replacements for the exact same entity throughout the entire transcript.",
                "But, two different entities cannot use the same anonymization replacement.",
                "",
                "",
                "In a second JSON Markdown block, format the report of the changes following the JSON Schema:",
                "```json",
                json.dumps(schema_changes, indent=1),
                "```",
                "",
            ])

            with transcript.open("r") as f:
                chatter.set_user_prompt([
                    "Please anonymize the following medical transcript while preserving all clinical information:",
                    "```json",
                    f.read(),
                    "```",
                    "",
                    "Follow rigorously the instructions and provide both JSON Markdown code block using the mentioned JSON Schemas.",
                ])
                if used_anonymizations:
                    chatter.set_user_prompt([
                        "The anonymized entities so far are:",
                        "```json",
                        json.dumps(list(used_anonymizations.values()), indent=1),
                        "```",
                        "",
                        "Include this list in your response to be sure you are not using the same anonymization value for different entities.",
                    ])

                response = chatter.chat([schema_anonymization, schema_changes])
                # the anonymized transcript
                with anonymized.open("w") as f2:
                    json.dump(response.content[0], f2, indent=2)
                # the used anonymization
                last_anonymizations = response.content[1]
                for anonymization in last_anonymizations:
                    used_anonymizations[anonymization["originalEntity"]] = anonymization

        return result

    @classmethod
    def schema_anonymization(cls) -> dict:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "array",
            "items": {
                "type": "object",
                "required": ["speaker", "text"],
                "properties": {
                    "speaker": {"type": "string", "minLength": 1},
                    "text": {"type": "string"},
                },
                "additionalProperties": False,
            },
        }

    @classmethod
    def schema_changes(cls) -> dict:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "array",
            "items": {
                "type": "object",
                "required": ["originalEntity", "anonymizedWith"],
                "properties": {
                    "originalEntity": {
                        "type": "string",
                        "description": "value of the original entity before replacement",
                    },
                    "anonymizedWith": {
                        "type": "string",
                        "description": "value of the replacement ; two different entities cannot use the same anonymization",
                    },
                },
                "additionalProperties": False,
            },
        }
