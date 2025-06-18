# mypy: allow-untyped-defs
import json
from pathlib import Path

import pytest

from evaluations.constants import Constants
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.audio_interpreter import AudioInterpreter


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if 'audio2transcript_files' in metafunc.fixturenames:
        # run all evaluation tests in the audio2transcript directory:
        # for each MP3 folder in the inputs_mp3 directory, there should be a
        # JSON file in the expected_json directory with the same name and the expected transcript
        input_dir = Path(__file__).parent / 'audio2transcript/inputs_mp3'
        expected_dir = Path(__file__).parent / 'audio2transcript/expected_json'
        files: list[tuple[str, str, list[Path], Path]] = []

        for mp3_folder in input_dir.glob('*'):
            if mp3_folder.is_dir() is False:
                continue

            json_file = expected_dir / f"{mp3_folder.stem}.json"
            assert json_file.exists(), f"{mp3_folder.stem}: no corresponding JSON file found"

            cycle_len = len(f"{Constants.CASE_CYCLE_SUFFIX}_???")
            cycles = json.load(json_file.open("r")).keys()
            cycled_mp3_files: dict[str, list[Path]] = {cycle: [] for cycle in cycles}
            for file in mp3_folder.glob(f"{Constants.CASE_CYCLE_SUFFIX}_???_??.mp3"):
                key = file.stem[:cycle_len]
                cycled_mp3_files[key].append(file)
            for cycle, mp3_files in cycled_mp3_files.items():
                files.append((json_file.stem, cycle, sorted(mp3_files, key=lambda x: x.stem), json_file))

        metafunc.parametrize('audio2transcript_files', files, ids=lambda path: f"{path[0]}_{path[1]}")


def test_audio2transcript(
        audio2transcript_files: tuple[str, str, list[Path], Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
)-> None:
    runner_audio2transcript(
        audio2transcript_files,
        allowed_levels,
        audio_interpreter,
        capsys,
        request,
    )


def runner_audio2transcript(
        audio2transcript_files: tuple[str, str, list[Path], Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
)-> None:
    case, cycle, mp3_files, json_file = audio2transcript_files
    content: list[bytes] = []
    for mp3_file in mp3_files:
        with mp3_file.open("rb") as f:
            content.append(f.read())

    expected = json.load(json_file.open('r')).get(cycle, [])

    transcript = audio_interpreter.combine_and_speaker_detection(content, "")
    assert transcript.has_error is False, f"{case}-{cycle}: transcript failed"

    valid, differences = HelperEvaluation.json_nuanced_differences(
        f"{case}-{cycle}-audio2transcript",
        allowed_levels,
        json.dumps(transcript.content, indent=1),
        json.dumps(expected, indent=1),
    )
    if not valid:
        request.node.user_properties.append(("llmExplanation", differences))
        with capsys.disabled():
            print(differences)
    assert valid, f"{case}-{cycle}: transcript incorrect"
