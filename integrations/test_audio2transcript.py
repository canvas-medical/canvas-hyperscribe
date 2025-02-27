import json
from pathlib import Path
from re import match

from integrations.helper_settings import HelperSettings


def pytest_generate_tests(metafunc):
    if 'audio2transcript_files' in metafunc.fixturenames:
        # run all integration tests in the audio2transcript directory:
        # for each MP3 file in the inputs_mp3 directory, there should be a
        # JSON file in the expected_json directory with the same name and the expected transcript
        input_dir = Path(__file__).parent / 'audio2transcript/inputs_mp3'
        expected_dir = Path(__file__).parent / 'audio2transcript/expected_json'
        files: list[tuple[list[Path], Path]] = []

        pattern = r'.+\.\d{2}\.mp3$'
        for mp3_file in input_dir.glob('*.mp3'):
            if match(pattern, mp3_file.name):
                continue
            json_file = expected_dir / f"{mp3_file.stem}.json"
            assert json_file.exists(), f"{mp3_file.stem}: no corresponding JSON file found"

            # sorted to have the file without index first
            mp3_files = sorted([file for file in input_dir.glob(f"{mp3_file.stem}*.mp3")], key=lambda x: f"{len(x.stem):03d}{x.stem}")

            files.append((mp3_files, json_file))

        metafunc.parametrize('audio2transcript_files', files, ids=lambda path: path[0][0].stem)


def test_audio2transcript(audio2transcript_files, allowed_levels, audio_interpreter, capsys):
    mp3_files, json_file = audio2transcript_files

    content: list[bytes] = []
    for mp3_file in mp3_files:
        with mp3_file.open("rb") as f:
            content.append(f.read())

    transcript = audio_interpreter.combine_and_speaker_detection(content)
    assert transcript.has_error is False, f"{mp3_files[0].stem}: transcript failed"

    with json_file.open('r') as f:
        expected = json.load(f)

    valid, differences = HelperSettings.json_nuanced_differences(
        allowed_levels,
        json.dumps(transcript.content, indent=1),
        json.dumps(expected, indent=1),
    )
    if not valid:
        with capsys.disabled():
            print(differences)
    assert valid, f"{mp3_files[0].stem}: transcript incorrect"
