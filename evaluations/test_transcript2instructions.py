import json
from pathlib import Path

import pytest

from evaluations.constants import Constants
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line


def test_transcript2instructions(
    transcript2instructions: tuple[str, str, Path],
    allowed_levels: list,
    audio_interpreter: AudioInterpreter,
    capsys: pytest.CaptureFixture[str],
    request: pytest.FixtureRequest,
) -> None:
    runner_transcript2instructions(transcript2instructions, allowed_levels, audio_interpreter, capsys, request)


def runner_transcript2instructions(
    transcript2instructions: tuple[str, str, Path],
    allowed_levels: list,
    audio_interpreter: AudioInterpreter,
    capsys: pytest.CaptureFixture[str],
    request: pytest.FixtureRequest,
) -> None:
    case, cycle, json_file = transcript2instructions
    content = json.load(json_file.open("r"))[cycle]

    lines = Line.load_from_json(content["transcript"])
    instructions = Instruction.load_from_json(content["instructions"]["initial"])
    for idx, instruction in enumerate(instructions):
        instruction.uuid = f"id{idx:02d}"
    expected = Instruction.load_from_json(content["instructions"]["result"])
    response = audio_interpreter.detect_instructions_per_section(lines, instructions)

    result = Instruction.load_from_json(response)
    assert len(result) == len(expected), (
        f"{[(i.instruction, i.information) for i in result]} != {[(i.instruction, i.information) for i in expected]}"
    )

    # order is not important for instruction of different types,
    # but it is within the same type
    expected.sort(key=lambda x: (x.instruction, x.is_new, x.is_updated))
    result.sort(key=lambda x: (x.instruction, x.is_new, x.is_updated))

    for actual, instruction in zip(result, expected):
        error_label = f"{case}-{cycle} {instruction.instruction}: information incorrect\n=>{instruction.information}<="
        if instruction.uuid not in ["", Constants.IGNORED_KEY_VALUE]:
            assert actual.uuid == instruction.uuid, error_label
        assert actual.instruction == instruction.instruction, error_label
        # assert actual.is_new == instruction.is_new, error_label
        # assert actual.is_updated == instruction.is_updated, error_label

        valid, differences = HelperEvaluation.text_nuanced_differences(
            f"{case}-{cycle}-transcript2instructions",
            allowed_levels,
            actual.information,
            instruction.information,
        )
        if not valid:
            request.node.user_properties.append(("llmExplanation", differences))
            with capsys.disabled():
                print(differences)
        assert valid, error_label
