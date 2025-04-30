import json
from pathlib import Path

from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters


def pytest_generate_tests(metafunc):
    if 'parameters2command' in metafunc.fixturenames:
        # run all evaluation tests in the parameters2command directory
        # in each JSON file, there should be:
        # - a set of instructions, and the related
        # - set of parameters
        # - set of commands
        files = list((Path(__file__).parent / 'parameters2command').glob('*.json'))
        if not files:
            return
        metafunc.parametrize('parameters2command', files, ids=lambda path: path.stem)


def test_parameters2command(parameters2command, allowed_levels, audio_interpreter, capsys, request):
    with parameters2command.open("r") as f:
        content = json.load(f)

    instructions = Instruction.load_from_json(content["instructions"])
    parameters = content["parameters"]
    expected = content["commands"]
    for idx, instruction in enumerate(instructions):
        response = audio_interpreter.create_sdk_command_from(InstructionWithParameters.add_parameters(instruction, parameters[idx]))

        error_label = f"{parameters2command.stem} {instruction.instruction} - {idx:02d}"
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
                f"{parameters2command.stem}-parameters2command",
                allowed_levels,
                json.dumps(automated, indent=1),
                json.dumps(reviewed, indent=1),
            )
            if not valid:
                request.node.user_properties.append(("llmExplanation", differences))
                with capsys.disabled():
                    print(differences)
            assert valid, error_label
