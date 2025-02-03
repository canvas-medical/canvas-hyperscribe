import json
from pathlib import Path

from commander.protocols.audio_interpreter import AudioInterpreter
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.instruction import Instruction
from commander.protocols.structures.line import Line
from integrations.helper_settings import HelperSettings


def pytest_generate_tests(metafunc):
    if 'transcript2instructions' in metafunc.fixturenames:
        # run all integration tests in the transcript2instructions directory
        # in each JSON file, there should be:
        # - a transcript
        # - a set of initial instructions
        # - a set of result instructions
        json_dir = Path(__file__).parent / 'transcript2instructions'
        metafunc.parametrize('transcript2instructions', json_dir.glob('*.json'), ids=lambda path: path.stem)


def test_transcript2instructions(transcript2instructions):
    Constants.HAS_DATABASE_ACCESS = False  # TODO to be changed when the SDK provides access to the database
    settings = HelperSettings.settings()

    audio_interpreter = AudioInterpreter(settings, "patientXYZ", "noteABC", "providerUVW")

    conversation = OpenaiChat(settings.openai_key, Constants.OPENAI_CHAT_TEXT)
    conversation.system_prompt = [
        "The user will provides two texts. ",
        "Your task is compare them *solely* from a meaning point of view and report the discrepancies as a JSON list in a Markdown block like:",
        "```json",
        json.dumps([
            {
                "level": "minor/mild/severe/critical",
                "difference": "description of the difference between the texts",
            }
        ]),
        "```",
    ]

    with transcript2instructions.open("r") as f:
        content = json.load(f)

    lines = Line.load_from_json(content["transcript"])
    instructions = Instruction.load_from_json(content["instructions"]["initial"])
    expected = Instruction.load_from_json(content["instructions"]["result"])
    response = audio_interpreter.detect_instructions(lines, instructions)

    assert response.has_error is False
    result = Instruction.load_from_json(response.content)
    assert len(result) == len(expected)

    for actual, instruction in zip(result, expected):
        if instruction.uuid:
            assert actual.uuid == instruction.uuid
        assert actual.instruction == instruction.instruction
        assert actual.is_new == instruction.is_new
        assert actual.is_updated == instruction.is_updated

        conversation.user_prompt = [
            "First text, called 'automated': ",
            "```text",
            actual.information,
            "```",
            "",
            "Second text, called 'reviewed': ",
            "```text",
            instruction.information,
            "```",
            "",
            "Please, review both texts and report as instructed all differences from a meaning point of view."
        ]
        chat = conversation.chat()
        excluded_minor_differences = [
            difference
            for difference in chat.content
            if difference["level"] not in ["minor"]
        ]
        assert excluded_minor_differences == [], f"{transcript2instructions.stem} {instruction.instruction}: information incorrect\n=>{instruction.information}<="
