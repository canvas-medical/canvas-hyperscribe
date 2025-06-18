# mypy: allow-untyped-defs
import json
from pathlib import Path

import pytest
from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.libraries.audio_interpreter import AudioInterpreter
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    step = 'parameters2command'
    if step in metafunc.fixturenames:
        files = HelperEvaluation.list_case_files(Path(__file__).parent / step)
        metafunc.parametrize(step, files, ids=lambda path: f"{path[0]}_{path[1]}")


def test_parameters2command(
        parameters2command: tuple[str, str, Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    runner_parameters2command(
        parameters2command,
        allowed_levels,
        audio_interpreter,
        capsys,
        request,
    )


def runner_parameters2command(
        parameters2command: tuple[str, str, Path],
        allowed_levels: list,
        audio_interpreter: AudioInterpreter,
        capsys: pytest.CaptureFixture[str],
        request: pytest.FixtureRequest,
) -> None:
    case, cycle, json_file = parameters2command
    content = json.load(json_file.open("r"))[cycle]

    instructions = Instruction.load_from_json(content["instructions"])
    parameters = content["parameters"]
    expected = content["commands"]
    for idx, instruction in enumerate(instructions):
        response = audio_interpreter.create_sdk_command_from(InstructionWithParameters.add_parameters(instruction, parameters[idx]))

        error_label = f"{case}-{cycle} {instruction.instruction} - {idx:02d}"
        assert response is not None, error_label
        command = response.command
        assert command.__class__.__module__ == expected[idx]["module"], error_label
        assert command.__class__.__name__ == expected[idx]["class"], error_label
        assert isinstance(command, BaseCommand), error_label

        forced = {
            "note_uuid": "theNoteUuid",
            "command_uuid": "theCommandUuid",
        }

        automated = command.values | forced
        reviewed = expected[idx]["attributes"] | forced

        if automated != reviewed:
            valid, differences = HelperEvaluation.json_nuanced_differences(
                f"{case}-{cycle}-parameters2command",
                allowed_levels,
                json.dumps(automated, indent=1),
                json.dumps(reviewed, indent=1),
            )
            if not valid:
                request.node.user_properties.append(("llmExplanation", differences))
                with capsys.disabled():
                    print(differences)
            assert valid, error_label
