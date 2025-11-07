import json
from pathlib import Path

import pytest

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.audio_interpreter import AudioInterpreter


def test_audio2transcript(
    audio2transcript_files: tuple[str, str, list[Path], Path],
    allowed_levels: list,
    audio_interpreter: AudioInterpreter,
    capsys: pytest.CaptureFixture[str],
    request: pytest.FixtureRequest,
) -> None:
    runner_audio2transcript(audio2transcript_files, allowed_levels, audio_interpreter, capsys, request)


def runner_audio2transcript(
    audio2transcript_files: tuple[str, str, list[Path], Path],
    allowed_levels: list,
    audio_interpreter: AudioInterpreter,
    capsys: pytest.CaptureFixture[str],
    request: pytest.FixtureRequest,
) -> None:
    case, cycle, mp3_files, json_file = audio2transcript_files
    content: list[bytes] = []
    for mp3_file in mp3_files:
        with mp3_file.open("rb") as f:
            content.append(f.read())

    expected = json.load(json_file.open("r")).get(cycle, [])

    # content[0] --> always use the first set of audio bytes
    transcript = audio_interpreter.combine_and_speaker_detection(content[0], [])
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
