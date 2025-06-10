# mypy: allow-untyped-defs
import json
from pathlib import Path

from canvas_sdk.commands import QuestionnaireCommand

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line


def pytest_generate_tests(metafunc):
    if 'staged_questionnaires' in metafunc.fixturenames:
        # run all evaluation tests in the staged_questionnaires directory
        # in each JSON file, there should be:
        # - a transcript
        # - a set of instructions, and the expected
        # - set of commands
        files = list((Path(__file__).parent / 'staged_questionnaires').glob('*.json'))
        if not files:
            return
        metafunc.parametrize('staged_questionnaires', files, ids=lambda path: path.stem)


def test_staged_questionnaires(staged_questionnaires, allowed_levels, audio_interpreter, capsys, request):
    with staged_questionnaires.open("r") as f:
        content = json.load(f)

    lines = Line.load_from_json(content["transcript"])
    instructions = Instruction.load_from_json(content["instructions"])
    for idx, instruction in enumerate(instructions):
        instruction.uuid = f"id{idx:02d}"

    expected = content["commands"]
    for idx, instruction in enumerate(instructions):
        response = audio_interpreter.update_questionnaire(lines, instruction)

        error_label = f"{staged_questionnaires.stem} {instruction.instruction} - {idx:02d}"
        assert response is not None, error_label
        command = response.command
        assert command.__class__.__module__ == expected[idx]["module"], error_label
        assert command.__class__.__name__ == expected[idx]["class"], error_label
        assert isinstance(command, QuestionnaireCommand), error_label

        forced = {
            "note_uuid": "theNoteUuid",
            "command_uuid": "theCommandUuid",
        }
        automated = command.values | forced
        reviewed = expected[idx]["attributes"] | forced

        if automated != reviewed:
            valid, differences = HelperEvaluation.json_nuanced_differences(
                f"{staged_questionnaires.stem}-staged_questionnaires",
                allowed_levels,
                json.dumps(automated, indent=1),
                json.dumps(reviewed, indent=1),
            )
            if not valid:
                request.node.user_properties.append(("llmExplanation", differences))
                with capsys.disabled():
                    print(differences)
            assert valid, error_label
