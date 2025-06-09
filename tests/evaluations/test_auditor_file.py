from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.auditor_file import AuditorFile
from hyperscribe.libraries.auditor import Auditor
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line


def test_auditor_file():
    tested = AuditorFile
    assert issubclass(tested, Auditor)


def test___init__():
    tested = AuditorFile("theCase")
    assert tested.case == "theCase"


@patch.object(AuditorFile, "case_files_from")
def test_case_files(case_files_from):
    def reset_mocks():
        case_files_from.reset_mock()

    tested = AuditorFile("theCase")
    case_files_from.side_effect = [
        ["file01", "file02"],
        ["file03", "file04", "file05"],
        ["file06", "file07", "file08", "file09"],
        ["file10"],
        ["file11", "file12"],
        ["file13", "file14", "file15"],
    ]
    result = [f for f in tested.case_files()]
    expected = [
        "file01",
        "file02",
        "file03",
        "file04",
        "file05",
        "file06",
        "file07",
        "file08",
        "file09",
        "file10",
        "file11",
        "file12",
        "file13",
        "file14",
        "file15",
    ]
    assert result == expected
    calls = [
        call('audio2transcript/inputs_mp3', 'mp3'),
        call('audio2transcript/expected_json', 'json'),
        call('transcript2instructions', 'json'),
        call('instruction2parameters', 'json'),
        call('parameters2command', 'json'),
        call('staged_questionnaires', 'json'),
    ]
    assert case_files_from.mock_calls == calls
    reset_mocks()


@patch("evaluations.auditor_file.Path.__truediv__")
def test_case_files_from(concat):
    mock_file = MagicMock()

    def reset_mocks():
        concat.reset_mock()
        mock_file.reset_mock()

    files = [
        Path("theCase.ext"),
        Path("theCase.txt"),
        Path("theCaseA.ext"),
        Path("theCase1.ext"),
        Path("theCase_cycle01.ext"),
        Path("theCase_cycle02.ext"),
        Path("theCase.01.txt"),
    ]

    tests = [
        ("theCase", "ext", "theCase*.ext", [Path("theCase.ext"), Path("theCase_cycle01.ext"), Path("theCase_cycle02.ext")]),
        ("theCase", "txt", "theCase*.txt", [Path("theCase.txt"), Path("theCase.01.txt")]),
        ("theCaseA", "txt", "theCaseA*.txt", []),
        ("theCaseA", "ext", "theCaseA*.ext", [Path("theCaseA.ext")]),
    ]
    for case, extension, exp_glob, exp_files in tests:
        concat.side_effect = [mock_file]
        mock_file.glob.side_effect = [files]
        tested = AuditorFile(case)
        result = [p for p in tested.case_files_from("the/folder", extension)]
        assert result == exp_files

        calls = [call('the/folder')]
        assert concat.mock_calls == calls
        calls = [call.glob(exp_glob)]
        assert mock_file.mock_calls == calls
        reset_mocks()


@patch.object(AuditorFile, 'case_files')
def test_is_ready(case_files):
    def reset_mocks():
        case_files.reset_mock()

    tested = AuditorFile("theCase")
    # there is no file
    case_files.side_effect = [[]]
    result = tested.is_ready()
    assert result is True
    calls = [call()]
    assert case_files.mock_calls == calls
    reset_mocks()
    # there is one file
    case_files.side_effect = [["file"]]
    result = tested.is_ready()
    assert result is False
    calls = [call()]
    assert case_files.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, 'case_files')
def test_reset(case_files):
    mock_files = [MagicMock(), MagicMock()]

    def reset_mocks():
        case_files.reset_mock()
        for item in mock_files:
            item.reset_mock()

    tested = AuditorFile("theCase")

    # there is no file
    case_files.side_effect = [[]]
    tested.reset()
    calls = [call()]
    assert case_files.mock_calls == calls
    for mock_file in mock_files:
        assert mock_file.mock_calls == []
    reset_mocks()

    # there is one file
    case_files.side_effect = [mock_files]
    tested.reset()
    calls = [call()]
    assert case_files.mock_calls == calls
    calls = [call.unlink(True)]
    for mock_file in mock_files:
        assert mock_file.mock_calls == calls
    reset_mocks()


@patch("evaluations.auditor_file.Path")
def test_identified_transcript(path):
    written_text = []
    written_bytes = []

    def write(line: str | bytes):
        if isinstance(line, bytes):
            written_bytes.append(line)
        else:
            written_text.append(line)

    def reset_mocks():
        path.reset_mock()

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


@patch("evaluations.auditor_file.Path")
def test_found_instructions(path):
    written_text = []

    def write(line: str):
        written_text.append(line)

    def reset_mocks():
        path.reset_mock()

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
                Instruction(uuid="uuid1", index=0, instruction="theInstruction1", information="theInformation0", is_new=False, is_updated=False),
            ],
            [
                Instruction(uuid="uuid1", index=0, instruction="theInstruction1", information="theInformation1", is_new=False, is_updated=True),
                Instruction(uuid="uuid2", index=1, instruction="theInstruction2", information="theInformation2", is_new=True, is_updated=False),
                Instruction(uuid="uuid3", index=2, instruction="theInstruction3", information="theInformation3", is_new=True, is_updated=False),
            ],
        )
        assert result is test

        expected = {'instructions': {
            'initial': [
                {
                    'index': 0,
                    'information': 'theInformation0',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': '>?<',
                },
            ],
            'result': [
                {
                    'index': 0,
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': True,
                    'uuid': '>?<',
                },
                {
                    'index': 1,
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': True,
                    'isUpdated': False,
                    'uuid': '>?<',
                },
                {
                    'index': 2,
                    'information': 'theInformation3',
                    'instruction': 'theInstruction3',
                    'isNew': True,
                    'isUpdated': False,
                    'uuid': '>?<',
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


@patch("evaluations.auditor_file.Path")
def test_computed_parameters(path):
    def write(line: str):
        written_text.append(line)

    def reset_mocks():
        path.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    sdk_parameters = [
        InstructionWithParameters(
            uuid="uuid1",
            index=1,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
            parameters={"key1": "parameter1"},
        ),
        InstructionWithParameters(
            uuid="uuid2",
            index=2,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
            parameters={"key2": "parameter2"},
        ),
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
                    'index': 1,
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': True,
                    'uuid': 'uuid1',
                },
                {
                    'index': 2,
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': True,
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
                        'index': 0,
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
                    'index': 0,
                    'information': 'theInformation0',
                    'instruction': 'theInstruction0',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid0',
                },
                {
                    'index': 1,
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': True,
                    'uuid': 'uuid1',
                },
                {
                    'index': 2,
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': True,
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


@patch("evaluations.auditor_file.Path")
def test_computed_commands(path):
    def write(line: str):
        written_text.append(line)

    commands = [MagicMock(), MagicMock()]

    def reset_mocks():
        for cmd in commands:
            cmd.reset_mock()
        path.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    for idx, command in enumerate(commands):
        command.__module__ = f"module{idx + 1}"
        command.__class__.__name__ = f"Class{idx + 1}"
        command.values = {f"key{idx + 1}": f"value{idx + 1}"}

    sdk_parameters = [
        InstructionWithCommand(
            uuid="uuid1",
            index=1,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
            parameters={"key1": "parameter1"},
            command=commands[0],
        ),
        InstructionWithCommand(
            uuid="uuid2",
            index=2,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=True,
            is_updated=False,
            parameters={"key2": "parameter2"},
            command=commands[1],
        ),
    ]

    # file does not exist yet
    tests = [True, False]
    for test in tests:
        written_text = []
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [False, test]
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.write = write

        tested = AuditorFile("theCase")
        result = tested.computed_commands(sdk_parameters)
        assert result is test

        expected = {
            'instructions': [
                {
                    'index': 1,
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': True,
                    'uuid': 'uuid1',
                },
                {
                    'index': 2,
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': True,
                    'isUpdated': False,
                    'uuid': 'uuid2',
                },
            ],
            'parameters': [
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
            "commands": [
                {"attributes": {"key1": "value1", "command_uuid": ">?<", "note_uuid": ">?<"}, "class": "Class1", "module": "module1"},
                {"attributes": {"key2": "value2", "command_uuid": ">?<", "note_uuid": ">?<"}, "class": "Class2", "module": "module2"},
            ],
        }
        assert json.loads("".join(written_text)) == expected

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
                        'index': 0,
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
        result = tested.computed_commands(sdk_parameters)
        assert result is test

        expected = {
            'instructions': [
                {
                    'index': 0,
                    'information': 'theInformation0',
                    'instruction': 'theInstruction0',
                    'isNew': False,
                    'isUpdated': False,
                    'uuid': 'uuid0',
                },
                {
                    'index': 1,
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': True,
                    'uuid': 'uuid1',
                },
                {
                    'index': 2,
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': True,
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
                {"attributes": {"key1": "value1", "command_uuid": ">?<", "note_uuid": ">?<"}, "class": "Class1", "module": "module1"},
                {"attributes": {"key2": "value2", "command_uuid": ">?<", "note_uuid": ">?<"}, "class": "Class2", "module": "module2"},
            ],
        }
        assert json.loads("".join(written_text)) == expected

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


@patch("evaluations.auditor_file.Path")
def test_computed_questionnaires(path):
    written_text = []

    def write(line: str):
        written_text.append(line)

    commands = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        for cmd in commands:
            cmd.reset_mock()
        path.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    for idx, command in enumerate(commands):
        command.__module__ = f"module{idx + 1}"
        command.__class__.__name__ = f"Class{idx + 1}"
        command.values = {
            f"key{idx + 1}": f"value{idx + 1}",
            "command_uuid": f"commandUuid{idx + 1}",
            "note_uuid": f"noteUuid{idx + 1}",
        }

    transcript = [
        Line(speaker="voiceA", text="theText1"),
        Line(speaker="voiceB", text="theText2"),
        Line(speaker="voiceB", text="theText3"),
        Line(speaker="voiceA", text="theText4"),
    ]
    initial_instructions = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation1",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="theInformation2",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid3",
            index=2,
            instruction="theInstruction3",
            information="theInformation3",
            is_new=False,
            is_updated=True,
        ),
    ]
    instructions_with_command = [
        InstructionWithCommand(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="changedInformation1",
            is_new=False,
            is_updated=True,
            parameters={},
            command=commands[0],
        ),
        InstructionWithCommand(
            uuid="uuid2",
            index=1,
            instruction="theInstruction2",
            information="changedInformation2",
            is_new=False,
            is_updated=True,
            parameters={},
            command=commands[1],
        ),
        InstructionWithCommand(
            uuid="uuid3",
            index=2,
            instruction="theInstruction3",
            information="changedInformation3",
            is_new=False,
            is_updated=True,
            parameters={},
            command=commands[2],
        ),
    ]
    tests = [True, False]
    for test in tests:
        written_text = []
        path.return_value.parent.__truediv__.return_value.exists.side_effect = [test]
        path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.write = write

        tested = AuditorFile("theCase")
        result = tested.computed_questionnaires(transcript, initial_instructions, instructions_with_command)
        assert result is test

        expected = {
            "instructions": [
                {
                    'index': 0,
                    'information': 'theInformation1',
                    'instruction': 'theInstruction1',
                    'isNew': False,
                    'isUpdated': True,
                    'uuid': '>?<',
                },
                {
                    'index': 1,
                    'information': 'theInformation2',
                    'instruction': 'theInstruction2',
                    'isNew': False,
                    'isUpdated': True,
                    'uuid': '>?<',
                },
                {
                    'index': 2,
                    'information': 'theInformation3',
                    'instruction': 'theInstruction3',
                    'isNew': False,
                    'isUpdated': True,
                    'uuid': '>?<',
                },
            ],
            "commands": [
                {"class": "Class1", "module": "module1", "attributes": {"key1": "value1", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"class": "Class2", "module": "module2", "attributes": {"key2": "value2", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"class": "Class3", "module": "module3", "attributes": {"key3": "value3", "command_uuid": ">?<", "note_uuid": ">?<"}},
            ],
            "transcript": [
                {"speaker": "voiceA", "text": "theText1"},
                {"speaker": "voiceB", "text": "theText2"},
                {"speaker": "voiceB", "text": "theText3"},
                {"speaker": "voiceA", "text": "theText4"},
            ],
        }
        assert json.loads("".join(written_text)) == expected

        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('staged_questionnaires/theCase.json'),
            call().parent.__truediv__().open('w'),
            call().parent.__truediv__().open().__enter__(),
            call().parent.__truediv__().open().__exit__(None, None, None),
            call().parent.__truediv__().exists(),
        ]
        assert path.mock_calls == calls
        reset_mocks()
