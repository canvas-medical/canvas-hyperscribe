import json
from pathlib import Path

from commander.protocols.audio_interpreter import AudioInterpreter
from commander.protocols.constants import Constants
from commander.protocols.openai_chat import OpenaiChat
from integrations.helper_settings import HelperSettings


def pytest_generate_tests(metafunc):
    if 'audio2transcript_files' in metafunc.fixturenames:
        # run all integration tests in the audio2transcript directory:
        # for each MP3 file in the inputs_mp3 directory, there should be a
        # JSON file in the expected_json directory with the same name and the expected transcript
        input_dir = Path(__file__).parent / 'audio2transcript/inputs_mp3'
        expected_dir = Path(__file__).parent / 'audio2transcript/expected_json'
        files: list[tuple[Path, Path]] = []
        for mp3_file in input_dir.glob('*.mp3'):
            json_file = expected_dir / f"{mp3_file.stem}.json"
            assert json_file.exists(), f"{mp3_file.stem}: no corresponding JSON file found"
            files.append((mp3_file, json_file))

        metafunc.parametrize('audio2transcript_files', files, ids=lambda path: path[0].stem)


def test_audio2transcript(audio2transcript_files):
    Constants.HAS_DATABASE_ACCESS = False  # TODO to be changed when the SDK provides access to the database
    settings = HelperSettings.settings()

    audio_interpreter = AudioInterpreter(settings, "patientXYZ", "noteABC", "providerUVW")

    mp3_file, json_file = audio2transcript_files
    with mp3_file.open("rb") as f:
        transcript = audio_interpreter.combine_and_speaker_detection([f.read()])
        assert transcript.has_error is False, f"{mp3_file.stem}: transcript failed"

    with json_file.open('r') as f:
        expected = json.load(f)

    conversation = OpenaiChat(settings.openai_key, Constants.OPENAI_CHAT_TEXT)
    conversation.system_prompt = [
        "The user will provides two JSON representing the transcript of a conversation or a monologue. ",
        "Your task is compare the transcripts *solely* from a meaning point of view and report the discrepancies as a JSON list in a Markdown block like:",
        "```json",
        json.dumps([
            {
                "level": "minor/mild/severe/critical",
                # "level": "syntax/meaning/grammar/punctuation/content",
                "difference": "description of the difference between the transcripts",
            }
        ]),
        "```",
    ]
    conversation.user_prompt = [
        "First transcript, called 'automated': ",
        "```json",
        json.dumps(transcript.content, indent=1),
        "```",
        "",
        "Second transcript, called 'reviewed': ",
        "```json",
        json.dumps(expected, indent=1),
        "```",
        "",
        "Please, review both transcripts and report as instructed all differences from a meaning point of view."
    ]
    result = conversation.chat()
    assert transcript.has_error is False, f"{mp3_file.stem}: comparison failed"
    excluded_minor_differences = [
        difference
        for difference in result.content
        if difference["level"] not in ["minor"]
    ]
    assert excluded_minor_differences == [], f"{mp3_file.stem}: transcript incorrect"
