from __future__ import annotations

import json
from io import StringIO
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
    tested = AuditorFile("theCase", 7)
    assert tested.case == "theCase"
    assert tested.cycle == 7


@patch("evaluations.auditor_file.Path")
@patch.object(AuditorFile, "case_file_from")
def test_case_files(case_file_from, path):
    mock_files = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]
    def reset_mocks():
        case_file_from.reset_mock()
        path.reset_mock()
        for idx, item in enumerate(mock_files):
            item.reset_mock()
            item.exists.side_effect = [bool(idx != 2)]

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tested = AuditorFile("theCase", 9)

    reset_mocks()
    # audios not included
    case_file_from.side_effect = mock_files
    path.return_value.parent.__truediv__.return_value.exists.side_effect = []

    result = [f for f in tested.case_files(False)]
    expected = [
        mock_files[0],
        mock_files[1],
        mock_files[3],
    ]
    assert result == expected
    calls = [
        call('transcript2instructions', 'json'),
        call('instruction2parameters', 'json'),
        call('parameters2command', 'json'),
        call('staged_questionnaires', 'json'),
    ]
    assert case_file_from.mock_calls == calls
    calls = [call.exists()]
    assert mock_files[0].mock_calls == calls
    assert mock_files[1].mock_calls == calls
    assert mock_files[2].mock_calls == calls
    assert mock_files[3].mock_calls == calls
    assert mock_files[4].mock_calls == []
    assert path.mock_calls == []
    reset_mocks()

    # audios are included
    # -- audio folder exists
    case_file_from.side_effect = mock_files
    path.return_value.parent.__truediv__.return_value.exists.side_effect = [True]
    path.return_value.parent.__truediv__.return_value.glob.side_effect = [
        [mock_files[5], mock_files[6], mock_files[7]],
    ]

    result = [f for f in tested.case_files(True)]
    expected = [
        mock_files[0],
        mock_files[1],
        mock_files[3],
        mock_files[4],
        mock_files[5],
        mock_files[6],
        mock_files[7],
    ]
    assert result == expected
    calls = [
        call('transcript2instructions', 'json'),
        call('instruction2parameters', 'json'),
        call('parameters2command', 'json'),
        call('staged_questionnaires', 'json'),
        call('audio2transcript/expected_json', 'json'),
    ]
    assert case_file_from.mock_calls == calls
    calls = [call.exists()]
    assert mock_files[0].mock_calls == calls
    assert mock_files[1].mock_calls == calls
    assert mock_files[2].mock_calls == calls
    assert mock_files[3].mock_calls == calls
    assert mock_files[4].mock_calls == calls
    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('audio2transcript/inputs_mp3/theCase'),
        call().parent.__truediv__().exists(),
        call().parent.__truediv__().glob('cycle_???_??.mp3')
    ]
    assert path.mock_calls == calls
    reset_mocks()
    # -- audio folder does not exist
    case_file_from.side_effect = mock_files
    path.return_value.parent.__truediv__.return_value.exists.side_effect = [False]
    path.return_value.parent.__truediv__.return_value.glob.side_effect = []

    result = [f for f in tested.case_files(True)]
    expected = [
        mock_files[0],
        mock_files[1],
        mock_files[3],
        mock_files[4],
    ]
    assert result == expected
    calls = [
        call('transcript2instructions', 'json'),
        call('instruction2parameters', 'json'),
        call('parameters2command', 'json'),
        call('staged_questionnaires', 'json'),
        call('audio2transcript/expected_json', 'json'),
    ]
    assert case_file_from.mock_calls == calls
    calls = [call.exists()]
    assert mock_files[0].mock_calls == calls
    assert mock_files[1].mock_calls == calls
    assert mock_files[2].mock_calls == calls
    assert mock_files[3].mock_calls == calls
    assert mock_files[4].mock_calls == calls
    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('audio2transcript/inputs_mp3/theCase'),
        call().parent.__truediv__().exists(),
    ]
    assert path.mock_calls == calls
    reset_mocks()


def test_case_file_from():
    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tested = AuditorFile("theCase", 9)
    result = tested.case_file_from("folder", "extension")
    expected = f"{directory}/folder/theCase.extension"
    assert result.as_posix() == expected


@patch.object(AuditorFile, 'case_files')
def test_is_ready(case_files):
    def reset_mocks():
        case_files.reset_mock()

    tested = AuditorFile("theCase", 7)
    # there is no file
    case_files.side_effect = [[]]
    result = tested.is_ready()
    assert result is True
    calls = [call(False)]
    assert case_files.mock_calls == calls
    reset_mocks()
    # there is one file
    case_files.side_effect = [["file"]]
    result = tested.is_ready()
    assert result is False
    calls = [call(False)]
    assert case_files.mock_calls == calls
    reset_mocks()


@patch("evaluations.auditor_file.Path")
@patch.object(AuditorFile, 'case_files')
def test_reset(case_files, path):
    mock_files = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        case_files.reset_mock()
        path.reset_mock()
        for item in mock_files:
            item.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tested = AuditorFile("theCase", 7)

    for files in [[], mock_files]:

        # do not delete audios
        case_files.side_effect = [files]
        tested.reset(False)
        calls = [call(False)]
        assert case_files.mock_calls == calls
        assert path.mock_calls == []
        calls = []
        if files:
            calls.append(call.unlink(True))
        for mock_file in mock_files:
            assert mock_file.mock_calls == calls
        reset_mocks()

        # delete audios
        for audio_folder_exists in [True, False]:
            case_files.side_effect = [files]
            path.return_value.parent.__truediv__.return_value.exists.side_effect = [audio_folder_exists]
            tested.reset(True)
            calls = [call(True)]
            assert case_files.mock_calls == calls
            calls = [
                call(f'{directory}/auditor_file.py'),
                call().parent.__truediv__('audio2transcript/inputs_mp3/theCase'),
                call().parent.__truediv__().exists(),
            ]
            if audio_folder_exists:
                calls.append(call().parent.__truediv__().rmdir())
            assert path.mock_calls == calls
            calls = []
            if files:
                calls.append(call.unlink(True))
            for mock_file in mock_files:
                assert mock_file.mock_calls == calls
            reset_mocks()


@patch("evaluations.auditor_file.Path")
def test_transcript(path):
    mock_file = MagicMock()

    def reset_mocks():
        path.reset_mock()
        mock_file.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")
    content = {
        "cycle_000": [
            {"speaker": "speaker 1", "text": "text 1"},
            {"speaker": "speaker 2", "text": "text 2"},
            {"speaker": "speaker 1", "text": "text 3"},
        ],
        "cycle_001": [
            {"speaker": "speaker 1", "text": "text 4"},
        ],
        "cycle_002": [
            {"speaker": "speaker 2", "text": "text 5"},
            {"speaker": "speaker 1", "text": "text 6"},
        ]
    }

    # file does not exist
    path.return_value.parent.__truediv__.side_effect = [mock_file]
    mock_file.exists.side_effect = [False]
    tested = AuditorFile("theCase", 7)
    result = tested.transcript()
    assert result == []
    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('audio2transcript/expected_json/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [call.exists()]
    assert mock_file.mock_calls == calls
    reset_mocks()

    # file exist
    # -- cycle does not exist
    path.return_value.parent.__truediv__.side_effect = [mock_file]
    mock_file.exists.side_effect = [True]
    mock_file.open.return_value.read.side_effect = [json.dumps(content)]
    tested = AuditorFile("theCase", 7)
    result = tested.transcript()
    assert result == []
    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('audio2transcript/expected_json/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open().read(),
    ]
    assert mock_file.mock_calls == calls
    reset_mocks()
    # -- cycle exists
    path.return_value.parent.__truediv__.side_effect = [mock_file]
    mock_file.exists.side_effect = [True]
    mock_file.open.return_value.read.side_effect = [json.dumps(content)]
    tested = AuditorFile("theCase", 2)
    result = tested.transcript()
    expected = [
        Line(speaker='speaker 2', text='text 5'),
        Line(speaker='speaker 1', text='text 6'),
    ]
    assert result == expected
    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('audio2transcript/expected_json/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open().read(),
    ]
    assert mock_file.mock_calls == calls
    reset_mocks()


@patch("evaluations.auditor_file.Path")
def test_identified_transcript(path):
    audio_folder = MagicMock()
    audio_files = [MagicMock(), MagicMock(), MagicMock()]
    json_file = MagicMock()

    def reset_mocks():
        path.reset_mock()
        audio_folder.reset_mock()
        for item in audio_files:
            item.reset_mock()
        json_file.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tests = [
        (False, False),
        (True, False),
        (True, True),
        (False, True),
    ]
    for audio_folder_exists, json_file_exists in tests:
        path.return_value.parent.__truediv__.side_effect = [
            audio_folder,
            json_file,
        ]
        audio_folder.__truediv__.side_effect = [
            audio_files[0],
            audio_files[1],
            audio_files[2],
        ]
        buffers = [StringIO()]
        if json_file_exists:
            buffers.insert(0, StringIO(json.dumps({
                "cycle_006": [
                    {"speaker": "voiceA", "text": "theText0"},
                    {"speaker": "voiceB", "text": "theText1"}
                ]
            })))

        audio_folder.exists.side_effect = [audio_folder_exists]
        json_file.exists.side_effect = [json_file_exists, True]
        json_file.open.side_effect = buffers

        tested = AuditorFile("theCase", 7)
        result = tested.identified_transcript(
            [b"audio1", b"audio2", b"audio3"],
            [
                Line(speaker="voiceA", text="theText2"),
                Line(speaker="voiceB", text="theText3"),
                Line(speaker="voiceB", text="theText4"),
                Line(speaker="voiceA", text="theText5"),
            ],
        )
        assert result is True

        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('audio2transcript/inputs_mp3/theCase'),
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('audio2transcript/expected_json/theCase.json'),
        ]
        assert path.mock_calls == calls
        calls = [
            call.exists(),
        ]
        if audio_folder_exists is False:
            calls.append(call.mkdir())
        calls.extend([
            call.__truediv__('cycle_007_00.mp3'),
            call.__truediv__('cycle_007_01.mp3'),
            call.__truediv__('cycle_007_02.mp3'),
        ])
        assert audio_folder.mock_calls == calls
        for idx, item in enumerate(audio_files):
            calls = [
                call.open('wb'),
                call.open().__enter__(),
                call.open().__enter__().write(f'audio{idx + 1}'.encode()),
                call.open().__exit__(None, None, None),
            ]
            assert item.mock_calls == calls
        calls = [
            call.exists(),
        ]
        if json_file_exists is True:
            calls.append(call.open('r'))
        calls.extend([
            call.open('w'),
            call.exists(),
        ])
        assert json_file.mock_calls == calls

        expected = {}
        if json_file_exists:
            expected = {
                "cycle_006": [
                    {"speaker": "voiceA", "text": "theText0"},
                    {"speaker": "voiceB", "text": "theText1"}
                ]
            }

        expected["cycle_007"] = [
            {"speaker": "voiceA", "text": "theText2"},
            {"speaker": "voiceB", "text": "theText3"},
            {"speaker": "voiceB", "text": "theText4"},
            {"speaker": "voiceA", "text": "theText5"}
        ]
        assert buffers[-1].getvalue() == json.dumps(expected, indent=2)
        reset_mocks()


@patch("evaluations.auditor_file.Path")
def test_found_instructions(path):
    json_file = MagicMock()

    def reset_mocks():
        path.reset_mock()
        json_file.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tests = [True, False]
    for json_file_exists in tests:
        path.return_value.parent.__truediv__.side_effect = [json_file]
        buffers = [StringIO()]
        if json_file_exists:
            buffers.insert(0, StringIO(json.dumps({
                "cycle_006": ["some previous content"]
            })))
        json_file.exists.side_effect = [json_file_exists, True]
        json_file.open.side_effect = buffers

        tested = AuditorFile("theCase", 7)
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
        assert result is True

        expected: dict = {}
        if json_file_exists:
            expected = {
                "cycle_006": ["some previous content"]
            }
        expected["cycle_007"] = {
            'transcript': [
                {'speaker': 'voiceA', 'text': 'theText1'},
                {'speaker': 'voiceB', 'text': 'theText2'},
                {'speaker': 'voiceB', 'text': 'theText3'},
                {'speaker': 'voiceA', 'text': 'theText4'},
            ],
            'instructions': {
            'initial': [
                {
                    'uuid': '>?<',
                    'index': 0,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation0',
                    'isNew': False,
                    'isUpdated': False,
                },
            ],
                'result': [
                    {
                    'uuid': '>?<',
                    'index': 0,
                        'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                    },
                    {
                    'uuid': '>?<',
                    'index': 1,
                    'instruction': 'theInstruction2',
                        'information': 'theInformation2',
                    'isNew': True,
                    'isUpdated': False,
                    },
                    {
                    'uuid': '>?<',
                    'index': 2,
                        'instruction': 'theInstruction3',
                    'information': 'theInformation3',
                    'isNew': True,
                    'isUpdated': False,
                },
            ],
        },
        }
        assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('transcript2instructions/theCase.json'),
        ]
        assert path.mock_calls == calls
        calls = [
            call.exists(),
        ]
        if json_file_exists is True:
            calls.append(call.open('r'))
        calls.extend([
            call.open('w'),
            call.exists(),
        ])
        assert json_file.mock_calls == calls
        reset_mocks()


@patch("evaluations.auditor_file.Path")
def test_computed_parameters(path):
    json_file = MagicMock()

    def reset_mocks():
        path.reset_mock()
        json_file.reset_mock()

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

    # JSON file does not exist yet
    path.return_value.parent.__truediv__.side_effect = [json_file]
    buffers = [StringIO()]
    json_file.exists.side_effect = [False, True]
    json_file.open.side_effect = buffers

    tested = AuditorFile("theCase", 7)
    result = tested.computed_parameters(sdk_parameters)
    assert result is True

    expected = {
        "cycle_007": {
            'instructions': [
                {
                    'uuid': 'uuid1',
                    'index': 1,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': 'uuid2',
                    'index': 2,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': True,
                    'isUpdated': False,
                },
            ],
            'parameters': [
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
        },
    }
    assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('instruction2parameters/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    reset_mocks()
    # JSON file exists
    # -- cycle does not exist
    path.return_value.parent.__truediv__.side_effect = [json_file]
    buffers = [
        StringIO(json.dumps({
            "cycle_006": ["some previous content"]
        })),
        StringIO(),
    ]
    json_file.exists.side_effect = [True, True]
    json_file.open.side_effect = buffers

    tested = AuditorFile("theCase", 7)
    result = tested.computed_parameters(sdk_parameters)
    assert result is True

    expected = {
        "cycle_006": ["some previous content"],
        "cycle_007": {
            'instructions': [
                {
                    'uuid': 'uuid1',
                    'index': 1,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': 'uuid2',
                    'index': 2,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': True,
                    'isUpdated': False,
                },
            ],
            'parameters': [
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
        },
        }
    assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('instruction2parameters/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    reset_mocks()
    # -- cycle exists
    path.return_value.parent.__truediv__.side_effect = [json_file]
    buffers = [
        StringIO(json.dumps({
            "cycle_006": ["some previous content"],
            "cycle_007": {
                'instructions': [
                    {
                        'uuid': 'uuid0',
                        'index': 0,
                        'instruction': 'theInstruction0',
                        'information': 'theInformation0',
                        'isNew': False,
                        'isUpdated': True,
                    },
                ],
                'parameters': [
                    {"key0": "parameter0"},
                ],
            },
        })),
        StringIO(),
    ]
    json_file.exists.side_effect = [True, True]
    json_file.open.side_effect = buffers

    tested = AuditorFile("theCase", 7)
    result = tested.computed_parameters(sdk_parameters)
    assert result is True

    expected = {
        "cycle_006": ["some previous content"],
        "cycle_007": {
            'instructions': [
                {
                    'uuid': 'uuid0',
                    'index': 0,
                    'instruction': 'theInstruction0',
                    'information': 'theInformation0',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': 'uuid1',
                    'index': 1,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': 'uuid2',
                    'index': 2,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': True,
                    'isUpdated': False,
                },
            ],
            'parameters': [
                {"key0": "parameter0"},
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
        },
    }
    assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('instruction2parameters/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    reset_mocks()


@patch("evaluations.auditor_file.Path")
def test_computed_commands(path):
    json_file = MagicMock()
    commands = [MagicMock(), MagicMock()]

    def reset_mocks():
        path.reset_mock()
        json_file.reset_mock()
        for cmd in commands:
            cmd.reset_mock()

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

    # JSON file does not exist yet
    path.return_value.parent.__truediv__.side_effect = [json_file]
    buffers = [StringIO()]
    json_file.exists.side_effect = [False, True]
    json_file.open.side_effect = buffers

    tested = AuditorFile("theCase", 7)
    result = tested.computed_commands(sdk_parameters)
    assert result is True

    expected = {
        "cycle_007": {
            'instructions': [
                {
                    'uuid': 'uuid1',
                    'index': 1,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': 'uuid2',
                    'index': 2,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': True,
                    'isUpdated': False,
                },
            ],
            'parameters': [
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
            "commands": [
                {"module": "module1", "class": "Class1", "attributes": {"key1": "value1", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"module": "module2", "class": "Class2", "attributes": {"key2": "value2", "command_uuid": ">?<", "note_uuid": ">?<"}},
            ],
        },
    }
    assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('parameters2command/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    for command in commands:
        assert command.mock_calls == []
    reset_mocks()

    # JSON file exists
    # -- cycle does not exist
    path.return_value.parent.__truediv__.side_effect = [json_file]
    buffers = [
        StringIO(json.dumps({
            "cycle_006": ["some previous content"]
        })),
        StringIO(),
    ]
    json_file.exists.side_effect = [True, True]
    json_file.open.side_effect = buffers

    tested = AuditorFile("theCase", 7)
    result = tested.computed_commands(sdk_parameters)
    assert result is True

    expected = {
        "cycle_006": ["some previous content"],
        "cycle_007": {
            'instructions': [
                {
                    'uuid': 'uuid1',
                    'index': 1,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': 'uuid2',
                    'index': 2,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': True,
                    'isUpdated': False,
                },
            ],
            'parameters': [
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
            "commands": [
                {"module": "module1", "class": "Class1", "attributes": {"key1": "value1", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"module": "module2", "class": "Class2", "attributes": {"key2": "value2", "command_uuid": ">?<", "note_uuid": ">?<"}},
            ],
        },
    }
    assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('parameters2command/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    for command in commands:
        assert command.mock_calls == []
    reset_mocks()

    # -- cycle exists
    path.return_value.parent.__truediv__.side_effect = [json_file]
    buffers = [
        StringIO(json.dumps({
            "cycle_006": ["some previous content"],
            "cycle_007": {
                'instructions': [
                    {
                        'uuid': 'uuid0',
                        'index': 0,
                        'instruction': 'theInstruction0',
                        'information': 'theInformation0',
                        'isNew': False,
                        'isUpdated': False,
                    },
                ],
                'parameters': [{"key0": "parameter0"}],
                "commands": [
                    {"module": "module0", "class": "Class0", "attributes": {"key0": "value0"}},
                ],
            },
        })),
        StringIO(),
    ]
    json_file.exists.side_effect = [True, True]
    json_file.open.side_effect = buffers

    tested = AuditorFile("theCase", 7)
    result = tested.computed_commands(sdk_parameters)
    assert result is True

    expected = {
        "cycle_006": ["some previous content"],
        "cycle_007": {
            'instructions': [
                {
                    'uuid': 'uuid0',
                    'index': 0,
                    'instruction': 'theInstruction0',
                    'information': 'theInformation0',
                    'isNew': False,
                    'isUpdated': False,
                },
                {
                    'uuid': 'uuid1',
                    'index': 1,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': 'uuid2',
                    'index': 2,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': True,
                    'isUpdated': False,
                },
            ],
            'parameters': [
                {"key0": "parameter0"},
                {"key1": "parameter1"},
                {"key2": "parameter2"},
            ],
            "commands": [
                {"module": "module0", "class": "Class0", "attributes": {"key0": "value0"}},
                {"module": "module1", "class": "Class1", "attributes": {"key1": "value1", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"module": "module2", "class": "Class2", "attributes": {"key2": "value2", "command_uuid": ">?<", "note_uuid": ">?<"}},
            ],
        },
    }
    assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('parameters2command/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    for command in commands:
        assert command.mock_calls == []
    reset_mocks()



@patch("evaluations.auditor_file.Path")
def test_computed_questionnaires(path):
    json_file = MagicMock()

    commands = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        path.reset_mock()
        json_file.reset_mock()
        for cmd in commands:
            cmd.reset_mock()

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

    # JSON file does not exist yet
    path.return_value.parent.__truediv__.side_effect = [json_file]
    buffers = [StringIO()]
    json_file.exists.side_effect = [False, True]
    json_file.open.side_effect = buffers

    tested = AuditorFile("theCase", 7)
    result = tested.computed_questionnaires(transcript, initial_instructions, instructions_with_command)
    assert result is True

    expected = {
        "cycle_007": {
            "transcript": [
                {"speaker": "voiceA", "text": "theText1"},
                {"speaker": "voiceB", "text": "theText2"},
                {"speaker": "voiceB", "text": "theText3"},
                {"speaker": "voiceA", "text": "theText4"},
            ],
            "instructions": [
                {
                    'uuid': '>?<',
                    'index': 0,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': '>?<',
                    'index': 1,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': '>?<',
                    'index': 2,
                    'instruction': 'theInstruction3',
                    'information': 'theInformation3',
                    'isNew': False,
                    'isUpdated': True,
                },
            ],
            "commands": [
                {"module": "module1", "class": "Class1", "attributes": {"key1": "value1", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"module": "module2", "class": "Class2", "attributes": {"key2": "value2", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"module": "module3", "class": "Class3", "attributes": {"key3": "value3", "command_uuid": ">?<", "note_uuid": ">?<"}},
            ],
        },
    }
    assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('staged_questionnaires/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    for command in commands:
        assert command.mock_calls == []
    reset_mocks()

    # JSON file exists
    path.return_value.parent.__truediv__.side_effect = [json_file]
    buffers = [
        StringIO(json.dumps({
            "cycle_006": ["some previous content"]
        })),
        StringIO(),
    ]
    json_file.exists.side_effect = [True, True]
    json_file.open.side_effect = buffers

    tested = AuditorFile("theCase", 7)
    result = tested.computed_questionnaires(transcript, initial_instructions, instructions_with_command)
    assert result is True

    expected = {
        "cycle_006": ["some previous content"],
        "cycle_007": {
            "transcript": [
                {"speaker": "voiceA", "text": "theText1"},
                {"speaker": "voiceB", "text": "theText2"},
                {"speaker": "voiceB", "text": "theText3"},
                {"speaker": "voiceA", "text": "theText4"},
            ],
            "instructions": [
                {
                    'uuid': '>?<',
                    'index': 0,
                    'instruction': 'theInstruction1',
                    'information': 'theInformation1',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': '>?<',
                    'index': 1,
                    'instruction': 'theInstruction2',
                    'information': 'theInformation2',
                    'isNew': False,
                    'isUpdated': True,
                },
                {
                    'uuid': '>?<',
                    'index': 2,
                    'instruction': 'theInstruction3',
                    'information': 'theInformation3',
                    'isNew': False,
                    'isUpdated': True,
                },
            ],
            "commands": [
                {"module": "module1", "class": "Class1", "attributes": {"key1": "value1", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"module": "module2", "class": "Class2", "attributes": {"key2": "value2", "command_uuid": ">?<", "note_uuid": ">?<"}},
                {"module": "module3", "class": "Class3", "attributes": {"key3": "value3", "command_uuid": ">?<", "note_uuid": ">?<"}},
            ],
        },
    }
    assert buffers[-1].getvalue() == json.dumps(expected, indent=2)

    calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('staged_questionnaires/theCase.json'),
    ]
    assert path.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    for command in commands:
        assert command.mock_calls == []
    reset_mocks()
