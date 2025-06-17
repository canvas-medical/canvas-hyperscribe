# mypy: allow-untyped-defs
import json
from pathlib import Path

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.instruction import Instruction


def pytest_generate_tests(metafunc):
    step = 'instruction2parameters'
    if step in metafunc.fixturenames:
        # run all evaluation tests in the instruction2parameters directory
        # in each JSON file, there should be for each cycle:
        # - a set of instructions
        # - a set of parameters
        files = HelperEvaluation.list_case_files(Path(__file__).parent / step)
        metafunc.parametrize(step, files, ids=lambda path: f"{path[0]}_{path[1]}")


def test_instruction2parameters(instruction2parameters, allowed_levels, audio_interpreter, capsys, request):
    case, cycle, json_file = instruction2parameters
    content = json.load(json_file.open("r"))[cycle]

    instructions = Instruction.load_from_json(content["instructions"])
    expected = content["parameters"]
    for idx, instruction in enumerate(instructions):
        error_label = f"{case} {cycle} {instruction.instruction} - {idx:02d}"
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
