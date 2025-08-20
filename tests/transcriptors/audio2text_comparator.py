import json
from argparse import ArgumentParser, Namespace, ArgumentTypeError
from datetime import UTC
from datetime import datetime
from os import getenv, environ
from pathlib import Path
from time import time

from evaluations.constants import Constants as EvaluationConstants
from hyperscribe.libraries.constants import Constants as HyperscribeConstants
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.libraries.cached_sdk import CachedSdk
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.aws_s3_credentials import AwsS3Credentials
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.line import Line
from hyperscribe.structures.settings import Settings


class Audio2TextComparator:
    @classmethod
    def validate_files(cls, file_path: str) -> Path:
        file = Path(file_path)
        if not file.is_file():
            raise ArgumentTypeError(f"'{file_path}' is not a valid file")
        return file

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(
            description="Run the AudioInterpreter.combine_and_speaker_detection method"
            " on the provided files for the specified LLMs"
        )
        parser.add_argument(
            "--mp3",
            required=True,
            nargs="+",
            type=cls.validate_files,
            help="List of MP3 files",
        )
        parser.add_argument(
            "--expected",
            type=cls.validate_files,
            help="JSON file with the expected transcript",
        )
        parser.add_argument(
            "--evaluation-difference-levels",
            action="store",
            default=",".join(
                [EvaluationConstants.DIFFERENCE_LEVEL_MINOR, EvaluationConstants.DIFFERENCE_LEVEL_MODERATE]
            ),
            help="Coma separated list of the levels of meaning difference that are accepted",
        )
        return parser.parse_args()

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()
        settings = HelperEvaluation.settings()
        aws_s3 = HelperEvaluation.aws_s3_credentials()
        audios = [audio.read_bytes() for audio in parameters.mp3]
        prefix = datetime.now(UTC).strftime("%Y%m%d_%H%M")

        print(f"MP3 files:")
        for file in parameters.mp3:
            print(f"- {file.name}")

        print(f"LLM Audio: {settings.llm_audio.vendor}")

        start = time()
        result = {
            cycle: [line.to_json() for line in transcript]
            for cycle, transcript in cls.audio2text(settings, aws_s3, audios, prefix).items()
        }
        print(f"audio2text run: {int((time() - start) * 1000)} ms")

        if parameters.expected:
            allowed_levels = parameters.evaluation_difference_levels
            expected = json.loads(parameters.expected.read_text())
            for cycle, transcript in result.items():
                valid, differences = HelperEvaluation.json_nuanced_differences(
                    f"{prefix}-comparator-{cycle}-audio2transcript-{settings.llm_audio.vendor}",
                    allowed_levels,
                    json.dumps(transcript, indent=1),
                    json.dumps(expected[cycle], indent=1),
                )
                if valid:
                    print(f"{cycle}: ✅ ")
                else:
                    print(f"{cycle}: ❌ ")
                    for difference in json.loads(differences)[0]:
                        print(difference["level"], difference["difference"])
                print()
        else:
            print(json.dumps(result, indent=1))

    @classmethod
    def audio2text(
        cls, settings: Settings, aws_s3: AwsS3Credentials, audios: list[bytes], log_prefix: str
    ) -> dict[str, list[Line]]:
        result: dict[str, list[Line]] = {}
        cache = LimitedCache.load_from_json({})
        identification = IdentificationParameters(
            patient_uuid="audio2text",
            note_uuid=f"{log_prefix}__{settings.llm_audio.vendor}",
            provider_uuid="",
            canvas_instance="theAudio2TextComparator",
        )
        discussion = CachedSdk.get_discussion(identification.note_uuid)
        audio_interpreter = AudioInterpreter(settings, aws_s3, cache, identification)
        transcript_tail: list[Line] = []
        for cycle, audio in enumerate(audios, start=1):
            discussion.set_cycle(cycle)
            response = audio_interpreter.combine_and_speaker_detection([audio], transcript_tail)
            if not response.has_error:
                key = f"cycle_{cycle:03d}"
                result[key] = Line.load_from_json(response.content)
                transcript_tail = Line.tail_of(result[key], settings.cycle_transcript_overlap)
        return result


if __name__ == "__main__":
    llm_to_tests = (getenv("Audio2TextLLMs") or "").split()
    for i in range(0, len(llm_to_tests), 2):
        environ[HyperscribeConstants.SECRET_AUDIO_LLM_VENDOR] = llm_to_tests[i].strip()
        environ[HyperscribeConstants.SECRET_AUDIO_LLM_KEY] = llm_to_tests[i + 1].strip()
        Audio2TextComparator.run()
