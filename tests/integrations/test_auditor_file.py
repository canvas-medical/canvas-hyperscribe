from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from hyperscribe.handlers.auditor import Auditor
from hyperscribe.handlers.structures.instruction import Instruction
from hyperscribe.handlers.structures.line import Line
from integrations.auditor_file import AuditorFile


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
    written_text = []
    written_bytes = []

    def write(line: str | bytes):
        if isinstance(line, bytes):
            written_bytes.append(line)
        else:
            written_text.append(line)

    def reset_mocks():
        path.reset_mock()
        reset.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tests = [True, False]
    for test in tests:
        written_text = []
        written_bytes = []
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [test]
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.write = write

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
        expected = [
            {'speaker': 'voiceA', 'text': 'theText1'},
            {'speaker': 'voiceB', 'text': 'theText2'},
            {'speaker': 'voiceB', 'text': 'theText3'},
            {'speaker': 'voiceA', 'text': 'theText4'},
        ]

        assert json.loads("".join(written_text)) == expected
        assert written_bytes == [b'audio1', b'audio2']

        calls = [call()]
        assert reset.mock_calls == calls
        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('audio2transcript/inputs_mp3/theCase.mp3'),
            call().parent.__truediv__().open('wb'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('audio2transcript/inputs_mp3/theCase.01.mp3'),
            call().parent.__truediv__().open('wb'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('audio2transcript/expected_json/theCase.json'),
            call().parent.__truediv__().open('w'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().exists()
        ]
        assert path.mock_calls == calls
        reset_mocks()


@patch("integrations.auditor_file.Path")
@patch.object(AuditorFile, "reset")
def test_found_instructions(reset, path):
    written_text = []

    def write(line: str):
        written_text.append(line)

    def reset_mocks():
        path.reset_mock()
        reset.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tests = [True, False]
    for test in tests:
        written_text = []
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [test]
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.write = write

        tested = AuditorFile("theCase")
        result = tested.found_instructions(
            [
                Line(speaker="voiceA", text="theText1"),
                Line(speaker="voiceB", text="theText2"),
                Line(speaker="voiceB", text="theText3"),
                Line(speaker="voiceA", text="theText4"),
            ],
            [
                Instruction(uuid="uuid1", instruction="theInstruction1", information="theInformation1", is_new=False, is_updated=False),
                Instruction(uuid="uuid2", instruction="theInstruction2", information="theInformation2", is_new=False, is_updated=False),
            ],
        )
        assert result is test

        expected = {'instructions': {
            'initial': [],
            'result': [
                {
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': True,
                    'isUpdated': False,
                    'uuid': '',
                },
                {
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': True,
                    'isUpdated': False,
                    'uuid': '',
                },
            ],
        },
            'transcript': [
                {'speaker': 'voiceA', 'text': 'theText1'},
                {'speaker': 'voiceB', 'text': 'theText2'},
                {'speaker': 'voiceB', 'text': 'theText3'},
                {'speaker': 'voiceA', 'text': 'theText4'},
            ],
        }
        assert json.loads("".join(written_text)) == expected

        calls = [call()]
        assert reset.mock_calls == calls
        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('transcript2instructions/theCase.json'),
            call().parent.__truediv__().open('w'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().exists(),
        ]
        assert path.mock_calls == calls
        reset_mocks()


@patch("integrations.auditor_file.Path")
@patch.object(AuditorFile, "reset")
def test_computed_parameters(reset, path):
    def write(line: str):
        written_text.append(line)

    def reset_mocks():
        path.reset_mock()
        reset.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    sdk_parameters = [
        (Instruction(
            uuid="uuid1",
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
         {"key1": "parameter1"}),
        (Instruction(
            uuid="uuid2",
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
        ),
         {"key2": "parameter2"}),
    ]

    # file does not exist yet
    tests = [False, True]
    for test in tests:
        written_text = []
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [False, test]
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.write = write

        tested = AuditorFile("theCase")
        result = tested.computed_parameters(sdk_parameters)
        assert result is test

        expected = {
            'instructions': [
                {
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid1',
                },
                {
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid2',
                },
            ],
            'parameters': [
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
        }
        assert json.loads("".join(written_text)) == expected

        calls = [call()]
        assert reset.mock_calls == calls
        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('instruction2parameters/theCase.json'),
            call().parent.__truediv__().exists(),
            call().parent.__truediv__().open('w'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().exists(),
        ]
        assert path.mock_calls == calls
        reset_mocks()

    # file already exists
    tests = [True, False]
    for test in tests:
        written_text = []
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [True, test]
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.write = write
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.read.side_effect = [
            json.dumps({
                'instructions': [
                    {
                        'information': 'theInformation0',
                        'instruction': 'theInstruction0',
                        'isNew': False,
                        'isUpdated': False,
                        'uuid': 'uuid0',
                    },
                ],
                'parameters': [{"key0": "parameter0"}],
            })
        ]

        tested = AuditorFile("theCase")
        result = tested.computed_parameters(sdk_parameters)
        assert result is test

        expected = {
            'instructions': [
                {
                    'information': 'theInformation0',
                    'instruction': 'theInstruction0',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid0',
                },
                {
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid1',
                },
                {
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid2',
                },
            ],
            'parameters': [
                {"key0": "parameter0"},
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
        }
        assert json.loads("".join(written_text)) == expected

        calls = [call()]
        assert reset.mock_calls == calls
        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('instruction2parameters/theCase.json'),
            call().parent.__truediv__().exists(),
            call().parent.__truediv__().open('r'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__enter__().read(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().open('w'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().exists(),
        ]
        assert path.mock_calls == calls
        reset_mocks()


@patch("integrations.auditor_file.Path")
@patch.object(AuditorFile, "reset")
def test_computed_commands(reset, path):
    def write(line: str):
        written_text.append(line)

    commands = [MagicMock(), MagicMock()]

    def reset_mocks():
        for cmd in commands:
            cmd.reset_mock()
        path.reset_mock()
        reset.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    for idx, command in enumerate(commands):
        command.__module__ = f"module{idx + 1}"
        command.__class__.__name__ = f"Class{idx + 1}"
        command.values = {f"key{idx + 1}": f"value{idx + 1}"}

    sdk_parameters = [
        (Instruction(
            uuid="uuid1",
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
         {"key1": "parameter1"}),
        (Instruction(
            uuid="uuid2",
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
        ),
         {"key2": "parameter2"}),
    ]

    # file does not exist yet
    tests = [True, False]
    for test in tests:
        written_text = []
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [False, test]
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.write = write

        tested = AuditorFile("theCase")
        result = tested.computed_commands(sdk_parameters, commands)
        assert result is test

        expected = {
            'instructions': [
                {
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid1',
                },
                {
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid2',
                },
            ],
            'parameters': [
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
            "commands": [
                {"attributes": {"key1": "value1"}, "class": "Class1", "module": "module1"},
                {"attributes": {"key2": "value2"}, "class": "Class2", "module": "module2"},
            ],
        }
        assert json.loads("".join(written_text)) == expected

        calls = [call()]
        assert reset.mock_calls == calls
        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('parameters2command/theCase.json'),
            call().parent.__truediv__().exists(),
            call().parent.__truediv__().open('w'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().exists(),
        ]
        assert path.mock_calls == calls
        for command in commands:
            assert command.mock_calls == []
        reset_mocks()

    # file already exists
    tests = [[True, False]]
    for test in tests:
        written_text = []
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [True, test]
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.write = write
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.read.side_effect = [
            json.dumps({
                'instructions': [
                    {
                        'information': 'theInformation0',
                        'instruction': 'theInstruction0',
                        'isNew': False,
                        'isUpdated': False,
                        'uuid': 'uuid0',
                    },
                ],
                'parameters': [{"key0": "parameter0"}],
                "commands": [
                    {"attributes": {"key0": "value0"}, "class": "Class0", "module": "module0"},
                ],
            })
        ]

        tested = AuditorFile("theCase")
        result = tested.computed_commands(sdk_parameters, commands)
        assert result is test

        expected = {
            'instructions': [
                {
                    'information': 'theInformation0',
                    'instruction': 'theInstruction0',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid0',
                },
                {
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid1',
                },
                {
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid2',
                },
            ],
            'parameters': [
                {"key0": "parameter0"},
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
            "commands": [
                {"attributes": {"key0": "value0"}, "class": "Class0", "module": "module0"},
                {"attributes": {"key1": "value1"}, "class": "Class1", "module": "module1"},
                {"attributes": {"key2": "value2"}, "class": "Class2", "module": "module2"},
            ],
        }
        assert json.loads("".join(written_text)) == expected

        calls = [call()]
        assert reset.mock_calls == calls
        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('parameters2command/theCase.json'),
            call().parent.__truediv__().exists(),
            call().parent.__truediv__().open('r'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__enter__().read(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().open('w'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().exists(),
        ]
        assert path.mock_calls == calls
        reset_mocks()
