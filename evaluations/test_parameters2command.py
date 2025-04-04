import json
from pathlib import Path

from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.instruction import Instruction


def pytest_generate_tests(metafunc):
    if 'parameters2command' in metafunc.fixturenames:
        # run all evaluation tests in the parameters2command directory
        # in each JSON file, there should be:
        # - a set of instructions, and the related
        # - set of parameters
        # - set of commands
        json_dir = Path(__file__).parent / 'parameters2command'
        metafunc.parametrize('parameters2command', json_dir.glob('*.json'), ids=lambda path: path.stem)


def test_parameters2command(parameters2command, allowed_levels, audio_interpreter, capsys, request):
    with parameters2command.open("r") as f:
        content = json.load(f)

    instructions = Instruction.load_from_json(content["instructions"])
    parameters = content["parameters"]
    expected = content["commands"]
    for idx, instruction in enumerate(instructions):
        response = audio_interpreter.create_sdk_command_from(instruction, parameters[idx])

        assert response is not None
        assert response.__class__.__module__ == expected[idx]["module"]
        assert response.__class__.__name__ == expected[idx]["class"]
        assert isinstance(response, BaseCommand)

        forced = {
            "note_uuid": "theNoteUuid",
            "command_uuid": "theCommandUuid",
        }

        automated = response.values | forced
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
            assert valid, f"{parameters2command.stem} {instruction.instruction} - {idx:02d}"
