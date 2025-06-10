# mypy: allow-untyped-defs
import json
from pathlib import Path

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.instruction import Instruction


def pytest_generate_tests(metafunc):
    if 'instruction2parameters' in metafunc.fixturenames:
        # run all evaluation tests in the instruction2parameters directory
        # in each JSON file, there should be:
        # - a set of instructions
        # - a set of parameters
        files = list((Path(__file__).parent / 'instruction2parameters').glob('*.json'))
        if not files:
            return
        metafunc.parametrize('instruction2parameters', files, ids=lambda path: path.stem)


def test_instruction2parameters(instruction2parameters, allowed_levels, audio_interpreter, capsys, request):
    with instruction2parameters.open("r") as f:
        content = json.load(f)

    instructions = Instruction.load_from_json(content["instructions"])
    expected = content["parameters"]
    for idx, instruction in enumerate(instructions):
        error_label = f"{instruction2parameters.stem} {instruction.instruction} - {idx:02d}"
        response = audio_interpreter.create_sdk_command_parameters(instruction)
        assert response is not None, error_label
        if (automated := response.parameters) != (reviewed := expected[idx]):
            valid, differences = HelperEvaluation.json_nuanced_differences(
                f"{instruction2parameters.stem}-instruction2parameters",
                allowed_levels,
                json.dumps(automated, indent=1),
                json.dumps(reviewed, indent=1),
            )
            if not valid:
                request.node.user_properties.append(("llmExplanation", differences))
                with capsys.disabled():
                    print(differences)
            assert valid, error_label
