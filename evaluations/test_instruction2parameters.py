import json
from pathlib import Path

import pytest

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.structures.instruction import Instruction


def test_instruction2parameters(
        instruction2parameters: tuple[str, str, Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    runner_instruction2parameters(
        instruction2parameters,
        allowed_levels,
        audio_interpreter,
        capsys,
        request,
    )


def runner_instruction2parameters(
        instruction2parameters: tuple[str, str, Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    case, cycle, json_file = instruction2parameters
    content = json.load(json_file.open("r"))[cycle]

    instructions = Instruction.load_from_json(content["instructions"])
    expected = content["parameters"]
    for idx, instruction in enumerate(instructions):
        error_label = f"{case}-{cycle} {instruction.instruction} - {idx:02d}"
        response = audio_interpreter.create_sdk_command_parameters(instruction)
        assert response is not None, error_label
        if (automated := response.parameters) != (reviewed := expected[idx]):
            valid, differences = HelperEvaluation.json_nuanced_differences(
                f"{case}-{cycle}-instruction2parameters",
                allowed_levels,
                json.dumps(automated, indent=1),
                json.dumps(reviewed, indent=1),
            )
            if not valid:
                request.node.user_properties.append(("llmExplanation", differences))
                with capsys.disabled():
                    print(differences)
            assert valid, error_label
