import json
from pathlib import Path

from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.handlers.structures.instruction import Instruction
from hyperscribe.handlers.structures.line import Line


def pytest_generate_tests(metafunc):
    if 'transcript2instructions' in metafunc.fixturenames:
        # run all evaluation tests in the transcript2instructions directory
        # in each JSON file, there should be:
        # - a transcript
        # - a set of initial instructions
        # - a set of result instructions
        json_dir = Path(__file__).parent / 'transcript2instructions'
        metafunc.parametrize('transcript2instructions', json_dir.glob('*.json'), ids=lambda path: path.stem)


def test_transcript2instructions(transcript2instructions, allowed_levels, audio_interpreter, capsys):
    with transcript2instructions.open("r") as f:
        content = json.load(f)

    lines = Line.load_from_json(content["transcript"])
    instructions = Instruction.load_from_json(content["instructions"]["initial"])
    expected = Instruction.load_from_json(content["instructions"]["result"])
    response = audio_interpreter.detect_instructions(lines, instructions)

    result = Instruction.load_from_json(response)
    assert len(result) == len(expected)

    # order is not important for instruction of different types,
    # but it is within the same type
    expected.sort(key=lambda x: x.instruction)
    result.sort(key=lambda x: x.instruction)

    for actual, instruction in zip(result, expected):
        if instruction.uuid:
            assert actual.uuid == instruction.uuid
        assert actual.instruction == instruction.instruction
        assert actual.is_new == instruction.is_new
        assert actual.is_updated == instruction.is_updated

        valid, differences = HelperEvaluation.text_nuanced_differences(
            f"{transcript2instructions.stem}-transcript2instructions",
            allowed_levels,
            actual.information,
            instruction.information,
        )
        if not valid:
            with capsys.disabled():
                print(differences)
        assert valid, f"{transcript2instructions.stem} {instruction.instruction}: information incorrect\n=>{instruction.information}<="
