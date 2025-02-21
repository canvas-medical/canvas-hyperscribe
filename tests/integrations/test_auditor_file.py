from __future__ import annotations
from pathlib import Path
from unittest.mock import patch, call

from commander.protocols.auditor import Auditor
from commander.protocols.structures.line import Line
from integrations.auditor_file import AuditorFile


class PathMock:
    def __init__(self, path:str) -> None:
        self.path = Path(path)

    @property
    def parent(self) -> PathMock:
        return PathMock(self.path.parent.as_posix())


def test_auditor_file():
    tested = AuditorFile
    assert issubclass(tested, Auditor)


@patch.object(AuditorFile, "reset")
def test___init__(reset):
    def reset_mocks():
        reset.reset_mock()

    tested = AuditorFile("theCase")
    assert tested.case == "theCase"
    calls = [call()]
    assert reset.mock_calls == calls
    reset_mocks()


@patch("integrations.auditor_file.Path")
def test_reset(path):
    def reset_mocks():
        path.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")
    path.return_value.parent.__truediv__.return_value.glob.side_effect = [["file1", "file2"]]

    _ = AuditorFile("theCase")
    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('audio2transcript/inputs_mp3'),
        call().parent.__truediv__().glob('theCase*.mp3'),
        call('file1'),
        call().unlink(True),
        call('file2'),
        call().unlink(True),
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('audio2transcript/expected_json/theCase.json'),
        call().parent.__truediv__().unlink(True),
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('transcript2instructions/theCase.json'),
        call().parent.__truediv__().unlink(True),
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('instruction2parameters/theCase.json'),
        call().parent.__truediv__().unlink(True),
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('parameters2command/theCase.json'),
        call().parent.__truediv__().unlink(True),
    ]
    assert path.mock_calls == calls
    reset_mocks()


@patch("integrations.auditor_file.Path")
@patch.object(AuditorFile, "reset")
def test_identified_transcript(reset, path):
    def reset_mocks():
        path.reset_mock()
        reset.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tests = [True, False]
    for test in tests:
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [test]

        tested = AuditorFile("theCase")
        result = tested.identified_transcript(
            [b"audio1", b"audio2"],
            [
                Line(speaker="voiceA", text="theText1"),
                Line(speaker="voiceB", text="theText2"),
                Line(speaker="voiceB", text="theText3"),
                Line(speaker="voiceA", text="theText4"),
            ],
        )
        assert result is test
        calls = [call()]
        assert reset.mock_calls == calls
        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('audio2transcript/inputs_mp3/theCase.mp3'),
            call().parent.__truediv__().open('wb'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__enter__().write(b'audio1'),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('audio2transcript/inputs_mp3/theCase.01.mp3'),
            call().parent.__truediv__().open('wb'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__enter__().write(b'audio2'),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('audio2transcript/expected_json/theCase.json'),
            call().parent.__truediv__().open('w'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__enter__().write('[\n  '),
            call().parent.__truediv__().open().__enter__().write('[\n    "voiceA"'),
            call().parent.__truediv__().open().__enter__().write(',\n    "theText1"'),
            call().parent.__truediv__().open().__enter__().write('\n  '),
            call().parent.__truediv__().open().__enter__().write(']'),
            call().parent.__truediv__().open().__enter__().write(',\n  '),
            call().parent.__truediv__().open().__enter__().write('[\n    "voiceB"'),
            call().parent.__truediv__().open().__enter__().write(',\n    "theText2"'),
            call().parent.__truediv__().open().__enter__().write('\n  '),
            call().parent.__truediv__().open().__enter__().write(']'),
            call().parent.__truediv__().open().__enter__().write(',\n  '),
            call().parent.__truediv__().open().__enter__().write('[\n    "voiceB"'),
            call().parent.__truediv__().open().__enter__().write(',\n    "theText3"'),
            call().parent.__truediv__().open().__enter__().write('\n  '),
            call().parent.__truediv__().open().__enter__().write(']'),
            call().parent.__truediv__().open().__enter__().write(',\n  '),
            call().parent.__truediv__().open().__enter__().write('[\n    "voiceA"'),
            call().parent.__truediv__().open().__enter__().write(',\n    "theText4"'),
            call().parent.__truediv__().open().__enter__().write('\n  '),
            call().parent.__truediv__().open().__enter__().write(']'),
            call().parent.__truediv__().open().__enter__().write('\n'),
            call().parent.__truediv__().open().__enter__().write(']'),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().exists()
        ]
        assert path.mock_calls == calls
        reset_mocks()
