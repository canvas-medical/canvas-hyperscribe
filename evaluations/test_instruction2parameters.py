import json
from pathlib import Path

from hyperscribe.handlers.structures.instruction import Instruction
from evaluations.helper_settings import HelperSettings


def pytest_generate_tests(metafunc):
    if 'instruction2parameters' in metafunc.fixturenames:
        # run all evaluation tests in the instruction2parameters directory
        # in each JSON file, there should be:
        # - a set of instructions
        # - a set of parameters
        json_dir = Path(__file__).parent / 'instruction2parameters'
        metafunc.parametrize('instruction2parameters', json_dir.glob('*.json'), ids=lambda path: path.stem)


def test_instruction2parameters(instruction2parameters, allowed_levels, audio_interpreter, capsys):
    with instruction2parameters.open("r") as f:
        content = json.load(f)

    instructions = Instruction.load_from_json(content["instructions"])
    expected = content["parameters"]
    for idx, instruction in enumerate(instructions):
        _, response = audio_interpreter.create_sdk_command_parameters(instruction)
        if (automated := response) != (reviewed := expected[idx]):
            valid, differences = HelperSettings.json_nuanced_differences(
                f"{instruction2parameters.stem}-instruction2parameters",
                allowed_levels,
                json.dumps(automated, indent=1),
                json.dumps(reviewed, indent=1),
            )
            if not valid:
                with capsys.disabled():
                    print(differences)
            assert valid, f"{instruction2parameters.stem} {instruction.instruction} - {idx:02d}"
