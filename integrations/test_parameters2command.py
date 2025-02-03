import json
from pathlib import Path

from canvas_sdk.commands.base import _BaseCommand as BaseCommand

from commander.protocols.audio_interpreter import AudioInterpreter
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from commander.protocols.structures.instruction import Instruction
from integrations.helper_settings import HelperSettings


def pytest_generate_tests(metafunc):
    if 'parameters2command' in metafunc.fixturenames:
        # run all integration tests in the parameters2command directory
        # in each JSON file, there should be:
        # - a set of instructions, and the related
        # - set of parameters
        # - set of commands
        json_dir = Path(__file__).parent / 'parameters2command'
        metafunc.parametrize('parameters2command', json_dir.glob('*.json'), ids=lambda path: path.stem)


def test_parameters2command(parameters2command, capsys):
    Constants.HAS_DATABASE_ACCESS = False  # TODO to be changed when the SDK provides access to the database
    settings = HelperSettings.settings()

    audio_interpreter = AudioInterpreter(settings, "patientXYZ", "noteABC", "providerUVW")

    conversation = OpenaiChat(settings.openai_key, Constants.OPENAI_CHAT_TEXT)
    conversation.system_prompt = [
        "The user will provides two JSON objects. ",
        "Your task is compare them and report the discrepancies as a JSON list in a Markdown block like:",
        "```json",
        json.dumps([
            {
                "level": "minor/mild/severe/critical",
                "difference": "description of the difference between the JSONs",
            }
        ]),
        "```",
    ]

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
        if (automated := response.values) != (reviewed := expected[idx]["attributes"]):
            conversation.user_prompt = [
                "First JSON, called 'automated': ",
                "```json",
                json.dumps(automated, indent=1),
                "```",
                "",
                "Second JSON, called 'reviewed': ",
                "```json",
                json.dumps(reviewed, indent=1),
                "```",
                "",
                "Please, review both JSONs and report as instructed all differences."
            ]
            chat = conversation.chat()
            excluded_minor_differences = [
                difference
                for difference in chat.content
                if difference["level"] not in ["minor"]
            ]
            # with capsys.disabled():
            #     print("-------")
            #     print(chat.content)
            #     print("-------")
            assert excluded_minor_differences == [], f"{parameters2command.stem} {instruction.instruction} - {idx:02d}"
