# built by Claude, based on audio2text/audio2text_comparator.py

import json
import re
import threading
from argparse import ArgumentParser, Namespace, ArgumentTypeError
from datetime import UTC
from datetime import datetime
from os import getenv, environ
from pathlib import Path
from time import time
from typing import Optional

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


class ThreadResult:
    def __init__(self, vendor: str):
        self.vendor = vendor
        self.result: dict[str, list[Line]] = {}
        self.execution_time: int = 0
        self.combine_and_speaker_detection_time: int = 0
        self.validation_output: str = ""
        self.error: str = ""


class Audio2TextComparatorParallel:
    @classmethod
    def validate_directory(cls, dir_path: str) -> Path:
        directory = Path(dir_path)
        if not directory.is_dir():
            raise ArgumentTypeError(f"'{dir_path}' is not a valid directory")
        return directory

    @classmethod
    def _discover_files(cls, directory: Path) -> tuple[list[Path], Optional[Path]]:
        # Find all MP3 files
        mp3_files = list(directory.glob("*.mp3"))

        if not mp3_files:
            raise ValueError(f"No MP3 files found in directory {directory}")

        # Sort MP3 files by last 2 digits in filename
        def extract_last_digits(file_path: Path) -> int:
            match = re.search(r"(\d{2})\.mp3$", file_path.name)
            if match:
                return int(match.group(1))
            # If no 2-digit pattern found, try single digit with leading zero
            match = re.search(r"(\d)\.mp3$", file_path.name)
            if match:
                return int(match.group(1))
            # Fallback to full filename for sorting
            return 0

        mp3_files.sort(key=extract_last_digits)

        # Find JSON file (expected to be single .json file)
        json_files = list(directory.glob("*.json"))
        expected_file = json_files[0] if json_files else None

        return mp3_files, expected_file

    @classmethod
    def _parameters(cls) -> Namespace:
        parser = ArgumentParser(
            description="Run the AudioInterpreter.combine_and_speaker_detection method"
            " on MP3 files from a directory for the specified LLMs in parallel"
        )
        parser.add_argument(
            "--directory",
            required=True,
            type=cls.validate_directory,
            help="Directory containing MP3 files and expected JSON file",
        )
        parser.add_argument(
            "--evaluation-difference-levels",
            action="store",
            default=",".join(
                [
                    EvaluationConstants.DIFFERENCE_LEVEL_MINOR,
                    EvaluationConstants.DIFFERENCE_LEVEL_MODERATE,
                ]
            ),
            help="Coma separated list of the levels of meaning difference that are accepted",
        )
        return parser.parse_args()

    @classmethod
    def _worker_thread(
        cls,
        vendor: str,
        key: str,
        audios: list[bytes],
        prefix: str,
        aws_s3: AwsS3Credentials,
        result_container: dict[str, ThreadResult],
        lock: threading.Lock,
        expected_file: Path | None = None,
        allowed_levels: str = "",
    ) -> None:
        thread_result = ThreadResult(vendor)
        start_total = time()

        try:
            with lock:
                print(f"[{vendor}] Thread started")

            # Set environment variables for this thread
            environ[HyperscribeConstants.SECRET_AUDIO_LLM_VENDOR] = vendor
            environ[HyperscribeConstants.SECRET_AUDIO_LLM_KEY] = key

            settings = HelperEvaluation.settings()

            with lock:
                print(f"[{vendor}] LLM Audio: {settings.llm_audio.vendor}")

            start_audio2text = time()
            thread_result.result, thread_result.combine_and_speaker_detection_time = cls.audio2text(
                settings,
                aws_s3,
                audios,
                prefix,
                vendor,
                lock,
            )
            audio2text_time = int((time() - start_audio2text) * 1000)

            with lock:
                print(f"[{vendor}] audio2text run: {audio2text_time} ms")
                print(
                    f"[{vendor}] combine_and_speaker_detection cumulative: "
                    f"{thread_result.combine_and_speaker_detection_time} ms"
                )

            # Perform validation if expected file is provided
            if expected_file:
                allowed_levels_list = allowed_levels.split(",") if allowed_levels else []
                thread_result.validation_output = cls._validate_results(
                    thread_result.result,
                    expected_file,
                    allowed_levels_list,
                    prefix,
                    vendor,
                    lock,
                )
            else:
                # Convert results to JSON for output
                result_json = {
                    cycle: [line.to_json() for line in transcript] for cycle, transcript in thread_result.result.items()
                }
                thread_result.validation_output = json.dumps(result_json, indent=1)

            thread_result.execution_time = int((time() - start_total) * 1000)

            with lock:
                print(f"[{vendor}] Total thread execution time: {thread_result.execution_time} ms")

        except Exception as e:
            thread_result.error = str(e)
            thread_result.execution_time = int((time() - start_total) * 1000)
            with lock:
                print(f"[{vendor}] Error: {e}")

        result_container[vendor] = thread_result

    @classmethod
    def _validate_results(
        cls,
        result: dict[str, list[Line]],
        expected_file: Path,
        allowed_levels: list[str],
        prefix: str,
        vendor: str,
        lock: threading.Lock,
    ) -> str:
        validation_lines = []

        try:
            expected = json.loads(expected_file.read_text())
            result_json = {cycle: [line.to_json() for line in transcript] for cycle, transcript in result.items()}

            for cycle, transcript in result_json.items():
                valid, differences = HelperEvaluation.json_nuanced_differences(
                    f"{prefix}-comparator-{cycle}-audio2transcript-{vendor}",
                    allowed_levels,
                    json.dumps(transcript, indent=1),
                    json.dumps(expected[cycle], indent=1),
                )
                if valid:
                    validation_lines.append(f"[{vendor}] {cycle}: ✅ ")
                else:
                    validation_lines.append(f"[{vendor}] {cycle}: ❌ ")
                    for difference in json.loads(differences)[0]:
                        validation_lines.append(f"[{vendor}] {difference['level']}: {difference['difference']}")
                validation_lines.append("")
        except Exception as e:
            with lock:
                print(f"[{vendor}] Validation error: {e}")
            validation_lines.append(f"[{vendor}] Validation error: {e}")

        return "\n".join(validation_lines)

    @classmethod
    def run(cls) -> None:
        parameters = cls._parameters()

        # Discover MP3 and JSON files from directory
        mp3_files, expected_file = cls._discover_files(parameters.directory)

        aws_s3 = HelperEvaluation.aws_s3_credentials()
        audios = [audio.read_bytes() for audio in mp3_files]
        prefix = datetime.now(UTC).strftime("%Y%m%d_%H%M")

        print(f"Directory: {parameters.directory}")
        print(f"MP3 files (sorted by last 2 digits):")
        for file in mp3_files:
            print(f"- {file.name}")

        if expected_file:
            print(f"Expected file: {expected_file.name}")
        else:
            print("No expected JSON file found - will output raw results")

        # Parse LLM vendors and keys
        llm_to_tests = (getenv("Audio2TextLLMs") or "").split()
        if len(llm_to_tests) % 2 != 0:
            raise ValueError("Audio2TextLLMs must contain pairs of vendor and key")

        threads: list[threading.Thread] = []
        result_container: dict[str, ThreadResult] = {}
        lock = threading.Lock()

        # Create and start threads
        for i in range(0, len(llm_to_tests), 2):
            vendor = llm_to_tests[i].strip()
            key = llm_to_tests[i + 1].strip()

            thread = threading.Thread(
                target=cls._worker_thread,
                args=(
                    vendor,
                    key,
                    audios,
                    prefix,
                    aws_s3,
                    result_container,
                    lock,
                    expected_file,
                    parameters.evaluation_difference_levels,
                ),
            )
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Process results
        for vendor, thread_result in result_container.items():
            print(f"\n=== Results for {vendor} ===")
            print(f"Total execution time: {thread_result.execution_time} ms")
            print(f"combine_and_speaker_detection time: {thread_result.combine_and_speaker_detection_time} ms")

            if thread_result.error:
                print(f"Error: {thread_result.error}")
                continue

            # Print validation output (includes either validation results or JSON output)
            if thread_result.validation_output:
                print(thread_result.validation_output)

        # Final timing report
        print(f"\n=== Timing Summary ===")
        for vendor, thread_result in result_container.items():
            if not thread_result.error:
                print(f"{vendor}: {thread_result.combine_and_speaker_detection_time} ms")

    @classmethod
    def audio2text(
        cls,
        settings: Settings,
        aws_s3: AwsS3Credentials,
        audios: list[bytes],
        log_prefix: str,
        vendor: str,
        lock: threading.Lock,
    ) -> tuple[dict[str, list[Line]], int]:
        result: dict[str, list[Line]] = {}
        cumulative_combine_time: int = 0
        cache = LimitedCache.load_from_json({})
        identification = IdentificationParameters(
            patient_uuid="audio2text",
            note_uuid=f"{log_prefix}__{vendor}",
            provider_uuid="",
            canvas_instance="theAudio2TextComparator",
        )
        discussion = CachedSdk.get_discussion(identification.note_uuid)
        audio_interpreter = AudioInterpreter(settings, aws_s3, cache, identification)
        transcript_tail: list[Line] = []

        for cycle, audio in enumerate(audios, start=1):
            with lock:
                print(f"[{vendor}] Processing cycle {cycle}")

            discussion.set_cycle(cycle)

            # Time the combine_and_speaker_detection method specifically
            start_combine = time()
            response = audio_interpreter.combine_and_speaker_detection([audio], transcript_tail)
            cycle_combine_time = int((time() - start_combine) * 1000)
            cumulative_combine_time += cycle_combine_time

            if not response.has_error:
                key = f"cycle_{cycle:03d}"
                result[key] = Line.load_from_json(response.content)
                transcript_tail = Line.tail_of(result[key], settings.cycle_transcript_overlap)

                with lock:
                    print(
                        f"[{vendor}] Completed cycle {cycle} - combine_and_speaker_detection: {cycle_combine_time} ms"
                    )
            else:
                with lock:
                    print(f"[{vendor}] Error in cycle {cycle}: {response.error}")

        return result, cumulative_combine_time


if __name__ == "__main__":
    Audio2TextComparatorParallel.run()
