import json
from argparse import ArgumentParser
from argparse import Namespace
from http import HTTPStatus
from itertools import groupby
from pathlib import Path
from tempfile import TemporaryDirectory

import ffmpeg

from evaluations.auditors.auditor_postgres import AuditorPostgres
from evaluations.constants import Constants as EvaluationConstants
from evaluations.datastores.postgres.generated_note import GeneratedNote
from evaluations.datastores.postgres.real_world_case import RealWorldCase as RealWorldCaseStore
from evaluations.helper_evaluation import HelperEvaluation
from evaluations.structures.anonymization import Anonymization
from evaluations.structures.anonymization_error import AnonymizationError
from evaluations.structures.anonymization_substitution import AnonymizationSubstitution
from evaluations.structures.case_exchange import CaseExchange
from evaluations.structures.case_exchange_summary import CaseExchangeSummary
from evaluations.structures.records.real_world_case import RealWorldCase as RealWordCaseRecord
from hyperscribe.handlers.commander import Commander
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.aws_s3 import AwsS3
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.constants import Constants as HyperscribeConstants
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
    MAX_WORDS_PER_COMPACTED_TRANSCRIPT = 1000
    MAX_ANONYMIZATION_ATTEMPTS = 3

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
        parser.add_argument(
            "--path_temp_files",
            type=str,
            help="Folder to store temporary files, if provided, most existing files will be reused",
        )
        parser.add_argument(
            "--cycle_duration",
            type=int,
            required=True,
            help="Duration of each cycle, i.e. the duration of the audio chunks",
        )
        parser.add_argument("--force_refresh", action="store_true", help="Force refresh the temporary files")
        parser.add_argument("--force_rerun", action="store_true", help="Force rerun the cases generation")
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
            provider_uuid=HyperscribeConstants.FAUX_PROVIDER_UUID,
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
                parameters.cycle_duration,
                parameters.force_refresh,
                parameters.force_rerun,
            )
            instance._run()

    def __init__(
        self,
        settings: Settings,
        s3_credentials: AwsS3Credentials,
        identification: IdentificationParameters,
        output_dir: Path,
        cycle_duration: int,
        force_refresh: bool,
        force_rerun: bool,
    ) -> None:
        self.settings = settings
        self.s3_credentials = s3_credentials
        self.identification = identification
        self.output_dir = output_dir
        self.cycle_duration = cycle_duration
        self.force_refresh = force_refresh
        self.force_rerun = force_rerun

    def generate_case(
        self,
        limited_cache: LimitedCache,
        case_summary: CaseExchangeSummary,
        case_exchanges: list[CaseExchange],
    ) -> list[Instruction]:
        credentials = HelperEvaluation.postgres_credentials()

        auditor = AuditorPostgres(case_summary.title, 0, self.settings, self.s3_credentials, credentials)
        case_id, generated_note_id = GeneratedNote(credentials).last_run_for(case_summary.title)
        if case_id and generated_note_id and self.force_rerun is False:
            auditor._case_id = case_id
            auditor._generated_note_id = generated_note_id
            return auditor.summarized_generated_commands_as_instructions()

        chatter = AudioInterpreter(self.settings, self.s3_credentials, limited_cache, self.identification)
        previous = limited_cache.staged_commands_as_instructions(ImplementedCommands.schema_key2instruction())
        discussion = CachedSdk.get_discussion(chatter.identification.note_uuid)

        auditor.case_prepare()
        auditor.case_update_limited_cache(limited_cache.to_json(True))
        RealWorldCaseStore(credentials).upsert(
            RealWordCaseRecord(
                case_id=auditor.case_id(),
                customer_identifier=self.identification.canvas_instance,
                patient_note_hash=f"patient_{self.identification.patient_uuid}/note_{self.identification.note_uuid}",
                topical_exchange_identifier=case_summary.title,
                publishable=False,
                start_time=0.0,
                end_time=0.0,
                duration=0.0,
                audio_llm_vendor=self.settings.llm_audio.vendor,
                audio_llm_name=self.settings.llm_audio_model(),
            ),
        )
        errors: dict = {}
        try:
            cycle = 0
            for _, exchange in groupby(case_exchanges, key=lambda x: x.chunk):
                transcript = [Line(speaker=line.speaker, text=line.text) for line in exchange]
                cycle += 1
                discussion.set_cycle(cycle)
                auditor.set_cycle(cycle)
                auditor.upsert_json(
                    EvaluationConstants.AUDIO2TRANSCRIPT,
                    {auditor.cycle_key: [line.to_json() for line in transcript]},
                )
                previous, _ = Commander.transcript2commands(auditor, transcript, chatter, previous)
        except Exception as e:
            errors = HelperEvaluation.trace_error(e)
        finally:
            auditor.case_finalize(errors)
        return auditor.summarized_generated_commands_as_instructions()

    def create_transcripts(self, mp3_files: list[Path], interpreter: AudioInterpreter) -> list[Path]:
        result: list[Path] = []
        last_exchange: list[Line] = []
        for chunk, mp3_file in enumerate(mp3_files, 1):
            json_file = mp3_file.parent / f"transcript_{chunk:03d}.json"
            if self.force_refresh or not json_file.exists():
                with mp3_file.open("rb") as f:
                    audio_chunks = [f.read()]

                response = interpreter.combine_and_speaker_detection(audio_chunks, last_exchange)
                transcript = Line.load_from_json(response.content)
                with json_file.open("w") as f:
                    json.dump([line.to_json() for line in transcript], f, indent=2)

                last_exchange = Line.tail_of(transcript, interpreter.settings.cycle_transcript_overlap)

            result.append(json_file)
        return result

    def collated_webm_to_mp3(self) -> Path:
        client_s3 = AwsS3(self.s3_credentials)

        s3_folder = (
            f"hyperscribe-{self.identification.canvas_instance}/"
            f"patient_{self.identification.patient_uuid}/"
            f"note_{self.identification.note_uuid}"
        )

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
            (
                ffmpeg.input(webm_file.as_posix())
                .output(result.as_posix(), acodec="libmp3lame", ar=44100, ab="192k", vn=None)
                .overwrite_output()
                .run(overwrite_output=True, quiet=True)
            )
        return result

    def split_audio(self, audio_file: Path) -> list[Path]:
        result: list[Path] = []
        audio_file_str = audio_file.as_posix()
        probe = ffmpeg.probe(audio_file_str)
        duration = float(probe["format"]["duration"])
        chunk_index = 1
        chunk_time = 0.0

        while chunk_time < duration:
            end_time = min(chunk_time + self.cycle_duration, duration)
            chunk_file = audio_file.parent / f"{audio_file.stem}_{self.cycle_duration:03d}_{chunk_index:03d}.mp3"
            if self.force_refresh or chunk_file.exists() is False:
                (
                    ffmpeg.input(audio_file_str, ss=chunk_time, t=end_time - chunk_time)
                    .output(chunk_file.as_posix(), acodec="copy")
                    .overwrite_output()
                    .run(quiet=True)
                )

            chunk_time = end_time
            chunk_index += 1
            result.append(chunk_file)
        return result

    def anonymize_transcripts(self, transcript_files: list[Path]) -> list[Path]:
        result: list[Path] = []
        memory_log = MemoryLog.instance(self.identification, "anonymize_transcript", self.s3_credentials)

        used_anonymizations: dict[str, AnonymizationSubstitution] = {}
        for chunk, transcript in enumerate(transcript_files):
            anonymized = transcript.parent / f"transcript_anonymized_{chunk:03d}.json"
            result.append(anonymized)
            if anonymized.exists() and not self.force_refresh:
                continue

            anonymization = self.anonymize_transcripts_chat(memory_log, transcript, list(used_anonymizations.values()))
            with anonymized.open("w") as f2:
                json.dump([exchange.to_json() for exchange in anonymization.result], f2, indent=2)
            # the used anonymization
            for substitution in anonymization.substitutions:
                used_anonymizations[substitution.original_entity] = substitution

        return result

    def anonymize_transcripts_chat(
        self,
        memory_log: MemoryLog,
        transcript: Path,
        used_anonymizations: list[AnonymizationSubstitution],
    ) -> Anonymization:
        schema_anonymization = self.schema_anonymization()
        schema_changes = self.schema_changes()

        chatter = Helper.chatter(self.settings, memory_log)
        chatter.set_system_prompt(
            [
                "You are a medical transcript anonymization specialist with expertise in healthcare privacy compliance."
                "",
                "Your task is to remove all personally identifiable information (PII) from medical transcripts "
                "while preserving complete clinical context and medical accuracy through realistic replacements.",
                "",
                "**Anonymization Approach**",
                "Use realistic, plausible substitutions rather than placeholders:",
                "- Replace names with culturally appropriate alternatives of similar length/structure",
                "- Substitute locations with comparable geographic areas "
                "(similar urban/rural, climate, healthcare infrastructure)",
                "- Change dates, several days, and times while maintaining temporal relationships and seasonal "
                "context when medically relevant",
                "- Replace specific institutions with similar types (community hospital → regional medical center)",
                "- Replace any identification numbers, including but not limited to, zip code, phone, fax, "
                "social security, medical record, license plate, account, serial numbers, IP address, code",
                "- Generalize any other unique identifying numbers, characteristics, or codes "
                "that could be used to identify the individual or their household",
                "",
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
                "**Global Consistency**: Use identical replacements for the exact same entity "
                "throughout the entire transcript.",
                "But, two different entities cannot use the same anonymization replacement.",
                "",
                "",
                "In a second JSON Markdown block, format the report of the changes following the JSON Schema:",
                "```json",
                json.dumps(schema_changes, indent=1),
                "```",
                "",
            ],
        )

        with transcript.open("r") as f:
            source = f.read()
            chatter.set_user_prompt(
                [
                    "Please anonymize the following medical transcript while preserving all clinical information:",
                    "```json",
                    source,
                    "```",
                    "",
                    "Follow rigorously the instructions and provide both JSON Markdown code blocks using "
                    "the mentioned JSON Schemas.",
                ],
            )
            if used_anonymizations:
                chatter.set_user_prompt(
                    [
                        "Continue to used these anonymized entities:",
                        "```json",
                        json.dumps([used.to_json() for used in used_anonymizations], indent=1),
                        "```",
                        "",
                        "Also, include this list with any new substitution in your response to ensure you will used "
                        "the sames substitutions for uniquely the exact same entities (which means for the dates, "
                        "provide the full dates, not just the day of week)",
                    ],
                )

            for _ in range(self.MAX_ANONYMIZATION_ATTEMPTS):
                response = chatter.chat([schema_anonymization, schema_changes])
                result = Anonymization(
                    source=CaseExchange.load_from_json(json.loads(source)),
                    result=CaseExchange.load_from_json(response.content[0]),
                    substitutions=AnonymizationSubstitution.load_from_json(response.content[1]),
                )
                errors = self.anonymize_transcripts_check(memory_log, result)
                if not errors.has_errors:
                    break
                chatter.set_model_prompt(
                    [
                        "```json",
                        json.dumps(response.content[0], indent=1),
                        "```",
                        "```json",
                        json.dumps(response.content[1], indent=1),
                        "```",
                    ],
                )
                chatter.set_user_prompt(
                    [
                        "Here is the list of the errors you made in regards to the anonymization:",
                        "```json",
                        json.dumps(errors.errors, indent=1),
                        "```",
                        "",
                        "While still following rigorously the initial instructions, correct your response and "
                        "provide both JSON Markdown code blocks using "
                        "the mentioned JSON Schemas.",
                    ],
                )
            else:
                raise RuntimeError(f"Could not anonymize transcript: {transcript.as_posix()}")

            return result

    def anonymize_transcripts_check(self, memory_log: MemoryLog, anonymization: Anonymization) -> AnonymizationError:
        schema_errors = self.schema_errors()

        chatter = Helper.chatter(self.settings, memory_log)
        chatter.set_system_prompt(
            [
                "You are a validator of medical transcript anonymization with expertise in "
                "healthcare privacy compliance.",
                "",
                "The user will submit two transcripts: the original and the anonymized version.",
                "",
                "Your task is to identify any violations of anonymization rules based on the following principles:",
                "",
                "Any identifying information relating to an individual or to relatives, employers, or household "
                "members must be **replaced with realistic, synthetic alternatives** that do **not allow anyone "
                "to identify the actual individuals**. These replacements must be:",
                "",
                "- Plausible and coherent in context,",
                "- Non-traceable to the real identities,",
                "- Not obviously artificial (e.g. 'XXX' or 'Redacted' are invalid replacements).",
                "",
                "Substitution of identifiers with realistic but non-identifying values is considered fully compliant. "
                "You must **not report an error** if the original identifier was correctly substituted in a way that "
                "protects the individual's identity.",
                "",
                "Only report an error when:",
                "- The original identifier remains in the anonymized transcript,",
                "- The replacement is unrealistic or placeholder-like,",
                "- The replacement is still obviously identifying the real people,",
                "- The rules listed below are otherwise **blatantly** violated.",
                "",
                "The following identifiers **must** be anonymized through valid substitution:",
                "",
                "(A) Names;  ",
                "(B) All geographic subdivisions smaller than a State, including street address, city, county, "
                "precinct, zip code, and their equivalent geocodes;  ",
                "(C) All elements of dates (except year) for dates directly related to an individual, "
                "including birth date, admission date, discharge date, date of death;  ",
                "(D) Telephone numbers;  ",
                "(E) Fax numbers;  ",
                "(F) Electronic mail addresses;  ",
                "(G) Social security numbers;  ",
                "(H) Medical record numbers;  ",
                "(I) Health plan beneficiary numbers;  ",
                "(J) Account numbers;  ",
                "(K) Certificate/license numbers;  ",
                "(L) Vehicle identifiers and serial numbers, including license plate numbers;  ",
                "(M) Device identifiers and serial numbers;  ",
                "(N) Web Universal Resource Locators (URLs);  ",
                "(O) Internet Protocol (IP) address numbers;  ",
                "(P) Any other unique identifying number, characteristic, or code.",
                "",
                "Format your output strictly using this JSON Schema:",
                "```json",
                json.dumps(schema_errors, indent=1),
                "```",
                "",
            ],
        )
        chatter.set_user_prompt(
            [
                "The original transcript is:",
                "```json",
                json.dumps([exchange.to_json() for exchange in anonymization.source]),
                "```",
                "",
                "The anonymized transcript is:",
                "```json",
                json.dumps([exchange.to_json() for exchange in anonymization.result]),
                "```",
                "",
                "Follow rigorously the instructions and report any broken rules using the mentioned JSON Schema.",
                "If there is no issues, just send back an empty list in the JSON Markdown block.",
            ],
        )
        response = chatter.chat([schema_errors])
        return AnonymizationError(has_errors=bool(len(response.content[0]) > 0), errors=response.content[0])

    @classmethod
    def schema_anonymization(cls) -> dict:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "array",
            "items": {
                "type": "object",
                "required": ["speaker", "text", "chunk"],
                "properties": {
                    "speaker": {"type": "string", "minLength": 1},
                    "text": {"type": "string"},
                    "chunk": {"type": "integer"},
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
                        "description": "value of the replacement ; two different entities cannot "
                        "use the same anonymization",
                    },
                },
                "additionalProperties": False,
            },
        }

    @classmethod
    def schema_errors(cls) -> dict:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "array",
            "items": {
                "type": "object",
                "required": ["errorExplanation"],
                "properties": {
                    "errorExplanation": {
                        "type": "string",
                        "description": "full explanation of the deidentification error, "
                        "including the related text source and the broken rules",
                    },
                },
                "additionalProperties": False,
            },
        }

    @classmethod
    def schema_summary(cls) -> dict:
        return {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "pattern": "^[a-zA-Z0-9 ]+$",
                        "description": "a concise title composed with 25 to 40 characters",
                    },
                    "summary": {"type": "string", "description": "a summary of the exchange"},
                },
                "required": ["title", "summary"],
                "additionalProperties": False,
            },
        }

    @classmethod
    def compact_transcripts(cls, transcript_files: list[Path]) -> list[Path]:
        lines: list[CaseExchange] = []
        folder = transcript_files[0].parent
        result: list[Path] = [(folder / f"transcript_compacted_000.json")]
        words = 0
        for chunk, transcript in enumerate(transcript_files, start=1):
            with transcript.open("r") as f:
                for line in CaseExchange.load_from_json_default(json.load(f), chunk):
                    current = len(line.text.split())
                    if words + current < cls.MAX_WORDS_PER_COMPACTED_TRANSCRIPT:
                        words += current
                        lines.append(line)
                    else:
                        result.append(folder / f"transcript_compacted_{len(result):03d}.json")
                        words = current
                        lines = [line]
                    with result[-1].open("w") as f2:
                        json.dump([line.to_json() for line in lines], f2, indent=2)
        return result
