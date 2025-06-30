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
from tests.helper import is_constant, MockFile


def test_constant():
    tested = AuditorFile
    constants = {
        "AUDIOS_FOLDER": "audios",
        "AUDIO2TRANSCRIPT_FILE": "audio2transcript.json",
        "INSTRUCTION2PARAMETERS_FILE": "instruction2parameters.json",
        "PARAMETERS2COMMAND_FILE": "parameters2command.json",
        "STAGED_QUESTIONNAIRES_FILE": "staged_questionnaires.json",
        "TRANSCRIPT2INSTRUCTIONS_FILE": "transcript2instructions.json",
        "SUMMARY_JSON_INITIAL_FILE": "summary_initial.json",
        "SUMMARY_JSON_REVISED_FILE": "summary_revised.json",
        "SUMMARY_HTML_FILE": "summary.html",
    }
    assert is_constant(tested, constants)
def test_auditor_file():
    tested = AuditorFile
    assert issubclass(tested, Auditor)


def test___init__():
    tested = AuditorFile("theCase", 7)
    assert tested.case == "theCase"
    assert tested.cycle == 7


@patch("evaluations.auditor_file.Path")
def test_case_folder(path):
    folder = MagicMock()

    def reset_mocks():
        path.reset_mock()
        folder.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")
    tested = AuditorFile("theCase", 7)

    tests = [
        (False, [
            call.exists(),
            call.mkdir(),
        ]),
        (True, [
            call.exists(),
        ]),
    ]
    for folder_exists, exp_calls in tests:
        path.return_value.parent.__truediv__.side_effect = [folder]
        folder.exists.side_effect = [folder_exists]

        result = tested.case_folder()

        calls = [
            call(f'{directory}/auditor_file.py'),
            call().parent.__truediv__('cases/theCase'),
        ]
        assert path.mock_calls == calls
        assert folder.mock_calls == exp_calls

        assert result == folder
        reset_mocks()


@patch.object(AuditorFile, "case_folder")
def test_case_file(case_folder):
    def reset_mocks():
        case_folder.reset_mock()

    tested = AuditorFile("theCase", 7)

    case_folder.side_effect = [Path("/the/case/folder")]

    result = tested.case_file("theFile.ext")
    expected = Path("/the/case/folder/theFile.ext")
    assert result == expected
    calls = [call()]
    assert case_folder.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, "case_folder")
def test_audio_case_files(case_folder):
    audio_folder = MagicMock()

    def reset_mocks():
        case_folder.reset_mock()
        audio_folder.reset_mock()

    tested = AuditorFile("theCase", 7)

    # folder does not exist
    case_folder.return_value.__truediv__.side_effect = [audio_folder]
    audio_folder.exists.side_effect = [False]

    result = [f for f in tested.audio_case_files()]
    assert result == []
    calls = [
        call(),
        call().__truediv__('audios'),
    ]
    assert case_folder.mock_calls == calls
    calls = [call.exists()]
    assert audio_folder.mock_calls == calls
    reset_mocks()

    # folder exists
    files = [
        Path("/the/case/audios/folder/audio1.ext"),
        Path("/the/case/audios/folder/audio1.ext"),
        Path("/the/case/audios/folder/audio1.ext"),
    ]
    case_folder.return_value.__truediv__.side_effect = [audio_folder]
    audio_folder.exists.side_effect = [True]
    audio_folder.glob.side_effect = [files]

    result = [f for f in tested.audio_case_files()]
    assert result == files
    calls = [
        call(),
        call().__truediv__('audios'),
    ]
    assert case_folder.mock_calls == calls
    calls = [
        call.exists(),
        call.glob('cycle_???_??.mp3'),
    ]
    assert audio_folder.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, "case_file")
@patch.object(AuditorFile, "audio_case_files")
def test_case_files(audio_case_files, case_file):
    mock_files = [
        MagicMock(),
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
        audio_case_files.reset_mock()
        case_file.reset_mock()
        for idx, item in enumerate(mock_files):
            item.reset_mock()
            item.exists.side_effect = [bool(idx != 2)]

    tested = AuditorFile("theCase", 9)

    reset_mocks()

    # audios not included
    audio_case_files.side_effect = []
    case_file.side_effect = mock_files

    result = [f for f in tested.case_files(False)]
    expected = [
        mock_files[0],
        mock_files[1],
        mock_files[3],
        mock_files[4],
    ]
    assert result == expected
    calls = [
        call('instruction2parameters.json'),
        call('parameters2command.json'),
        call('staged_questionnaires.json'),
        call('transcript2instructions.json'),
        call('summary_initial.json'),
    ]
    assert case_file.mock_calls == calls
    assert audio_case_files.mock_calls == []
    calls = [call.exists()]
    for f in mock_files[:5]:
        assert f.mock_calls == calls
    for f in mock_files[5:]:
        assert f.mock_calls == []
    reset_mocks()

    # audios are included
    audio_case_files.side_effect = [mock_files[6:]]
    case_file.side_effect = mock_files

    result = [f for f in tested.case_files(True)]
    expected = [
        mock_files[6],
        mock_files[7],
        mock_files[8],
        mock_files[0],
        mock_files[1],
        mock_files[3],
        mock_files[4],
        mock_files[5],
    ]
    assert result == expected
    calls = [
        call('instruction2parameters.json'),
        call('parameters2command.json'),
        call('staged_questionnaires.json'),
        call('transcript2instructions.json'),
        call('summary_initial.json'),
        call('audio2transcript.json'),
    ]
    assert case_file.mock_calls == calls
    calls = [call()]
    assert audio_case_files.mock_calls == calls
    calls = [call.exists()]
    for f in mock_files[:6]:
        assert f.mock_calls == calls
    for f in mock_files[6:]:
        assert f.mock_calls == []
    reset_mocks()


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
@patch.object(AuditorFile, "case_file")
def test_is_complete(case_file, path):
    mock_files = [
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
        MagicMock(),
    ]

    def reset_mocks():
        case_file.reset_mock()
        path.reset_mock()
        for item in mock_files:
            item.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tested = AuditorFile("theCase", 9)

    # case folder does not exist
    path.return_value.parent.__truediv__.return_value.exists.side_effect = [False]
    case_file.side_effect = []

    result = tested.is_complete()
    assert result is False

    path_calls = [
        call(f'{directory}/auditor_file.py'),
        call().parent.__truediv__('cases/theCase'),
        call().parent.__truediv__().exists(),
    ]
    assert path.mock_calls == path_calls
    assert case_file.mock_calls == []
    for item in mock_files:
        assert item.mock_calls == []
    reset_mocks()

    # case folder exists
    # -- one file does not exist
    path.return_value.parent.__truediv__.return_value.exists.side_effect = [True]
    for idx, item in enumerate(mock_files):
        item.exists.side_effect = [bool(idx != 2)]

    case_file.side_effect = mock_files

    result = tested.is_complete()
    assert result is False

    assert path.mock_calls == path_calls
    calls = [
        call('instruction2parameters.json'),
        call('parameters2command.json'),
        call('staged_questionnaires.json'),
    ]
    assert case_file.mock_calls == calls
    calls = [call.exists()]
    for item in mock_files[:3]:
        assert item.mock_calls == calls
    for item in mock_files[3:]:
        assert item.mock_calls == []
    reset_mocks()
    # -- all files exist
    path.return_value.parent.__truediv__.return_value.exists.side_effect = [True]
    for idx, item in enumerate(mock_files):
        item.exists.side_effect = [True]

    case_file.side_effect = mock_files

    result = tested.is_complete()
    assert result is True

    assert path.mock_calls == path_calls
    calls = [
        call('instruction2parameters.json'),
        call('parameters2command.json'),
        call('staged_questionnaires.json'),
        call('transcript2instructions.json'),
        call('summary_initial.json'),
    ]
    assert case_file.mock_calls == calls
    calls = [call.exists()]
    for item in mock_files:
        assert item.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, 'case_folder')
@patch.object(AuditorFile, 'case_files')
def test_reset(case_files, case_folder):
    mock_files = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        case_files.reset_mock()
        case_folder.reset_mock()
        for item in mock_files:
            item.reset_mock()

    tested = AuditorFile("theCase", 7)

    for files in [[], mock_files]:

        # do not delete audios
        case_files.side_effect = [files]
        tested.reset(False)
        calls = [call(False)]
        assert case_files.mock_calls == calls
        assert case_folder.mock_calls == []
        calls = []
        if files:
            calls.append(call.unlink(True))
        for mock_file in mock_files:
            assert mock_file.mock_calls == calls
        reset_mocks()

        # delete audios
        for audio_folder_exists in [True, False]:
            case_files.side_effect = [files]
            case_folder.return_value.__truediv__.return_value.exists.side_effect = [audio_folder_exists]
            tested.reset(True)
            calls = [call(True)]
            assert case_files.mock_calls == calls
            calls = [
                call(),
                call().__truediv__('audios'),
                call().__truediv__().exists(),
            ]
            if audio_folder_exists:
                calls.append(call().__truediv__().rmdir())
            assert case_folder.mock_calls == calls
            calls = []
            if files:
                calls.append(call.unlink(True))
            for mock_file in mock_files:
                assert mock_file.mock_calls == calls
            reset_mocks()


@patch.object(AuditorFile, 'case_file')
def test_transcript(case_file):
    mock_file = MagicMock()

    def reset_mocks():
        case_file.reset_mock()
        mock_file.reset_mock()

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
    case_file.side_effect = [mock_file]
    mock_file.exists.side_effect = [False]
    tested = AuditorFile("theCase", 7)
    result = tested.transcript()
    assert result == []
    calls = [call("audio2transcript.json")]
    assert case_file.mock_calls == calls
    calls = [call.exists()]
    assert mock_file.mock_calls == calls
    reset_mocks()

    # file exist
    # -- cycle does not exist
    case_file.side_effect = [mock_file]
    mock_file.exists.side_effect = [True]
    mock_file.open.return_value.read.side_effect = [json.dumps(content)]
    tested = AuditorFile("theCase", 7)
    result = tested.transcript()
    assert result == []
    calls = [call("audio2transcript.json")]
    assert case_file.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open().read(),
    ]
    assert mock_file.mock_calls == calls
    reset_mocks()
    # -- cycle exists
    case_file.side_effect = [mock_file]
    mock_file.exists.side_effect = [True]
    mock_file.open.return_value.read.side_effect = [json.dumps(content)]
    tested = AuditorFile("theCase", 2)
    result = tested.transcript()
    expected = [
        Line(speaker='speaker 2', text='text 5'),
        Line(speaker='speaker 1', text='text 6'),
    ]
    assert result == expected
    calls = [call("audio2transcript.json")]
    assert case_file.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open().read(),
    ]
    assert mock_file.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, 'case_file')
@patch.object(AuditorFile, 'case_folder')
def test_identified_transcript(case_folder, case_file):
    audio_folder = MagicMock()
    audio_files = [MagicMock(), MagicMock(), MagicMock()]
    json_file = MagicMock()

    def reset_mocks():
        case_folder.reset_mock()
        case_file.reset_mock()
        audio_folder.reset_mock()
        for item in audio_files:
            item.reset_mock()
        json_file.reset_mock()


    tests = [
        (False, False),
        (True, False),
        (True, True),
        (False, True),
    ]
    for audio_folder_exists, json_file_exists in tests:
        case_file.side_effect = [json_file]
        case_folder.return_value.__truediv__.side_effect = [audio_folder]
        audio_folder.__truediv__.side_effect = [
            audio_files[0],
            audio_files[1],
            audio_files[2],
        ]
        buffers = [MockFile()]
        if json_file_exists:
            buffers.insert(0, MockFile(json.dumps({
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

        calls = [call('audio2transcript.json')]
        assert case_file.mock_calls == calls
        calls = [
            call(),
            call().__truediv__('audios'),
        ]
        assert case_folder.mock_calls == calls
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
        assert buffers[-1].content == json.dumps(expected, indent=2)
        reset_mocks()


@patch.object(AuditorFile, 'case_file')
def test_found_instructions(case_file):
    json_file = MagicMock()

    def reset_mocks():
        case_file.reset_mock()
        json_file.reset_mock()

    tests = [True, False]
    for json_file_exists in tests:
        case_file.side_effect = [json_file]
        buffers = [MockFile()]
        if json_file_exists:
            buffers.insert(0, MockFile(json.dumps({
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
        assert buffers[-1].content == json.dumps(expected, indent=2)

        calls = [call('transcript2instructions.json')]
        assert case_file.mock_calls == calls
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


@patch.object(AuditorFile, 'case_file')
def test_computed_parameters(case_file):
    json_file = MagicMock()

    def reset_mocks():
        case_file.reset_mock()
        json_file.reset_mock()

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
    case_file.side_effect = [json_file]
    buffers = [MockFile()]
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
    assert buffers[-1].content == json.dumps(expected, indent=2)

    calls = [call('instruction2parameters.json')]
    assert case_file.mock_calls == calls
    calls = [
        call.exists(),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    reset_mocks()
    # JSON file exists
    # -- cycle does not exist
    case_file.side_effect = [json_file]
    buffers = [
        MockFile(json.dumps({
            "cycle_006": ["some previous content"]
        })),
        MockFile(),
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
    assert buffers[-1].content == json.dumps(expected, indent=2)

    calls = [call('instruction2parameters.json')]
    assert case_file.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    reset_mocks()
    # -- cycle exists
    case_file.side_effect = [json_file]
    buffers = [
        MockFile(json.dumps({
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
        MockFile(),
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
    assert buffers[-1].content == json.dumps(expected, indent=2)

    calls = [call('instruction2parameters.json')]
    assert case_file.mock_calls == calls
    calls = [
        call.exists(),
        call.open('r'),
        call.open('w'),
        call.exists(),
    ]
    assert json_file.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, 'case_file')
def test_computed_commands(case_file):
    json_file = MagicMock()
    commands = [MagicMock(), MagicMock()]

    def reset_mocks():
        case_file.reset_mock()
        json_file.reset_mock()
        for cmd in commands:
            cmd.reset_mock()

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
    case_file.side_effect = [json_file]
    buffers = [MockFile()]
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
    assert buffers[-1].content == json.dumps(expected, indent=2)

    calls = [call('parameters2command.json')]
    assert case_file.mock_calls == calls
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
    case_file.side_effect = [json_file]
    buffers = [
        MockFile(json.dumps({
            "cycle_006": ["some previous content"]
        })),
        MockFile(),
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
    assert buffers[-1].content == json.dumps(expected, indent=2)

    calls = [call('parameters2command.json')]
    assert case_file.mock_calls == calls
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
    case_file.side_effect = [json_file]
    buffers = [
        MockFile(json.dumps({
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
        MockFile(),
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
    assert buffers[-1].content == json.dumps(expected, indent=2)

    calls = [call('parameters2command.json')]
    assert case_file.mock_calls == calls
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


@patch.object(AuditorFile, 'case_file')
def test_computed_questionnaires(case_file):
    json_file = MagicMock()

    commands = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        case_file.reset_mock()
        json_file.reset_mock()
        for cmd in commands:
            cmd.reset_mock()

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
    case_file.side_effect = [json_file]
    buffers = [MockFile()]
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
    assert buffers[-1].content == json.dumps(expected, indent=2)

    calls = [call('staged_questionnaires.json')]
    assert case_file.mock_calls == calls
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
    case_file.side_effect = [json_file]
    buffers = [
        MockFile(json.dumps({
            "cycle_006": ["some previous content"]
        })),
        MockFile(),
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
    assert buffers[-1].content == json.dumps(expected, indent=2)

    calls = [call('staged_questionnaires.json')]
    assert case_file.mock_calls == calls
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


@patch.object(AuditorFile, "case_file")
def test_summarized_generated_commands_as_instructions(case_file):
    def reset_mocks():
        case_file.reset_mock()

    tested = AuditorFile("theCase", 7)

    # there are no files for the case
    case_file.return_value.exists.side_effect = [False, False]

    result = tested.summarized_generated_commands_as_instructions()
    assert result == []
    calls = [
        call("parameters2command.json"),
        call().exists(),
        call("staged_questionnaires.json"),
        call().exists(),
    ]
    assert case_file.mock_calls == calls
    reset_mocks()

    # -- no commands in the files
    case_file.return_value.exists.side_effect = [True, True]
    case_file.return_value.open.return_value.read.side_effect = [
        json.dumps({}),
        json.dumps({}),
    ]

    result = tested.summarized_generated_commands_as_instructions()
    assert result == []

    calls = [
        call("parameters2command.json"),
        call().exists(),
        call().open('r'),
        call().open().read(),
        call("staged_questionnaires.json"),
        call().exists(),
        call().open('r'),
        call().open().read(),
    ]
    assert case_file.mock_calls == calls
    reset_mocks()

    # -- commands only in common commands
    case_file.return_value.exists.side_effect = [True, True]
    case_file.return_value.open.return_value.read.side_effect = [
        json.dumps({
            "cycle_000": {
                "instructions": [
                    {
                        "uuid": "uuid1",
                        "index": 0,
                        "instruction": "theInstruction1",
                        "information": "theInformation1",
                        "isNew": True,
                        "isUpdated": False,
                    },
                ],
            },
            "cycle_001": {
                "instructions": [
                    {
                        "uuid": "uuid1",
                        "index": 0,
                        "instruction": "theInstruction1",
                        "information": "theInformation2",
                        "isNew": False,
                        "isUpdated": True,
                    },
                    {
                        "uuid": "uuid3",
                        "index": 1,
                        "instruction": "theInstruction2",
                        "information": "theInformation3",
                        "isNew": True,
                        "isUpdated": False,
                    },
                ],
            },
            "cycle_002": {
                "instructions": [
                    {
                        "uuid": "uuid4",
                        "index": 2,
                        "instruction": "theInstruction3",
                        "information": "theInformation4",
                        "isNew": True,
                        "isUpdated": False,
                    },
                ],
            },
        }),
        json.dumps({}),
    ]

    result = tested.summarized_generated_commands_as_instructions()
    expected = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="theInstruction1",
            information="theInformation2",
            is_new=False,
            is_updated=True,
        ),
        Instruction(
            uuid="uuid3",
            index=1,
            instruction="theInstruction2",
            information="theInformation3",
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid4",
            index=2,
            instruction="theInstruction3",
            information="theInformation4",
            is_new=True,
            is_updated=False,
        ),
    ]
    assert result == expected

    assert case_file.mock_calls == calls
    reset_mocks()

    # -- commands only in questionnaire commands
    questionnaires = [
        {
            "name": "theQuestionnaire1",
            "dbid": 3,
            "questions": [
                {
                    "dbid": 9,
                    "label": "theRadioQuestion",
                    "type": "SING",
                    "skipped": None,
                    "responses": [
                        {"dbid": 25, "value": "Radio1", "selected": False, "comment": None},
                        {"dbid": 26, "value": "Radio2", "selected": False, "comment": None},
                        {"dbid": 27, "value": "Radio3", "selected": False, "comment": None},
                    ],
                },
                {
                    "dbid": 12,
                    "label": "theIntegerQuestion",
                    "type": "INT",
                    "skipped": None,
                    "responses": [
                        {"dbid": 41, "value": "", "selected": False, "comment": None},
                    ],
                }
            ]
        },
        {
            "name": "theQuestionnaire2",
            "dbid": 3,
            "questions": [
                {
                    "dbid": 10,
                    "label": "theCheckBoxQuestion",
                    "type": "MULT",
                    "skipped": None,
                    "responses": [
                        {"dbid": 33, "value": "Checkbox1", "selected": False, "comment": ""},
                        {"dbid": 34, "value": "Checkbox2", "selected": False, "comment": ""},
                        {"dbid": 35, "value": "Checkbox3", "selected": False, "comment": ""},
                    ]
                },
                {
                    "dbid": 11,
                    "label": "theTextQuestion",
                    "type": "TXT",
                    "skipped": None,
                    "responses": [
                        {"dbid": 37, "value": "", "selected": False, "comment": None},
                    ]
                },
                {
                    "dbid": 17,
                    "label": "otherTextQuestion",
                    "type": "TXT",
                    "skipped": None,
                    "responses": [
                        {"dbid": 51, "value": "", "selected": False, "comment": None},
                    ]
                },
            ]
        }
    ]
    case_file.return_value.exists.side_effect = [True, True]
    case_file.return_value.open.return_value.read.side_effect = [
        json.dumps({}),
        json.dumps({
            "cycle_000": {
                "instructions": [
                    {"uuid": "uuid1", "instruction": "questionnaireA", "information": json.dumps(questionnaires[0])},
                    {"uuid": "uuid2", "instruction": "questionnaireB", "information": json.dumps(questionnaires[1])},
                ],
                "commands": [
                    {
                        "module": "theModule1",
                        "class": "TheClass1",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "questions": {
                                "question-9": 999,
                                "question-12": 999,

                            },
                        },
                    },
                    {
                        "module": "theModule2",
                        "class": "TheClass2",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "questions": {
                                "question-10": [
                                    {
                                        "text": "Checkbox1",
                                        "value": 999,
                                        "comment": "",
                                        "selected": False,
                                    },
                                    {
                                        "text": "Checkbox2",
                                        "value": 999,
                                        "comment": "theComment2",
                                        "selected": True,
                                    },
                                    {
                                        "text": "Checkbox3",
                                        "value": 999,
                                        "comment": "",
                                        "selected": True,
                                    },
                                ],
                                "question-11": "theFreeText",
                            },
                        },
                    },
                ]},
            "cycle_002": {
                "instructions": [
                    {
                        "uuid": "uuid1",
                        "index": 0,
                        "instruction": "questionnaireA",
                        "information": json.dumps(questionnaires[0]),
                        "isNew": True,
                        "isUpdated": False,
                    },
                    {
                        "uuid": "uuid2",
                        "index": 1,
                        "instruction": "questionnaireB",
                        "information": json.dumps(questionnaires[1]),
                        "isNew": False,
                        "isUpdated": True,
                    },
                ],
                "commands": [
                    {
                        "module": "theModule1",
                        "class": "TheClass1",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "questions": {
                                "question-9": 26,
                                "question-12": 57,

                            },
                        },
                    },
                    {
                        "module": "theModule2",
                        "class": "TheClass2",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "questions": {
                                "question-10": [
                                    {
                                        "text": "Checkbox1",
                                        "value": 33,
                                        "comment": "",
                                        "selected": False,
                                    },
                                    {
                                        "text": "Checkbox2",
                                        "value": 34,
                                        "comment": "theComment2",
                                        "selected": True,
                                    },
                                    {
                                        "text": "Checkbox3",
                                        "value": 35,
                                        "comment": "",
                                        "selected": True,
                                    },
                                ],
                                "question-11": "theFreeText",
                            },
                        },
                    },
                ]},
        }),
    ]

    result = tested.summarized_generated_commands_as_instructions()
    expected = [
        Instruction(
            uuid="uuid1",
            index=0,
            instruction="questionnaireA",
            information=json.dumps({
                "name": "theQuestionnaire1",
                "dbid": 3,
                "questions": [
                    {
                        "dbid": 9,
                        "label": "theRadioQuestion",
                        "type": "SING",
                        "skipped": None,
                        "responses": [
                            {"dbid": 25, "value": "Radio1", "selected": False, "comment": None},
                            {"dbid": 26, "value": "Radio2", "selected": True, "comment": None},
                            {"dbid": 27, "value": "Radio3", "selected": False, "comment": None},
                        ]
                    },
                    {
                        "dbid": 12,
                        "label": "theIntegerQuestion",
                        "type": "INT",
                        "skipped": None,
                        "responses": [
                            {"dbid": 41, "value": 57, "selected": True, "comment": None},
                        ]
                    }
                ]
            }
            ),
            is_new=True,
            is_updated=False,
        ),
        Instruction(
            uuid="uuid2",
            index=1,
            instruction="questionnaireB",
            information=json.dumps({
                "name": "theQuestionnaire2",
                "dbid": 3,
                "questions": [
                    {
                        "dbid": 10,
                        "label": "theCheckBoxQuestion",
                        "type": "MULT",
                        "skipped": None,
                        "responses": [
                            {"dbid": 33, "value": "Checkbox1", "selected": False, "comment": ""},
                            {"dbid": 34, "value": "Checkbox2", "selected": True, "comment": "theComment2"},
                            {"dbid": 35, "value": "Checkbox3", "selected": True, "comment": ""},
                        ]
                    },
                    {
                        "dbid": 11,
                        "label": "theTextQuestion",
                        "type": "TXT",
                        "skipped": None,
                        "responses": [
                            {"dbid": 37, "value": "theFreeText", "selected": True, "comment": None},
                        ]
                    },
                    {
                        "dbid": 17,
                        "label": "otherTextQuestion",
                        "type": "TXT",
                        "skipped": None,
                        "responses": [
                            {"dbid": 51, "value": "", "selected": False, "comment": None},
                        ]
                    }
                ]
            }
            ),
            is_new=False,
            is_updated=True,
        ),
    ]
    assert result == expected

    assert case_file.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, "case_file")
def test_summarized_generated_commands(case_file):
    def reset_mocks():
        case_file.reset_mock()

    tested = AuditorFile("theCase", 7)

    # there are no files for the case
    case_file.return_value.exists.side_effect = [False, False]

    result = tested.summarized_generated_commands()
    assert result == []
    calls = [
        call("parameters2command.json"),
        call().exists(),
        call("staged_questionnaires.json"),
        call().exists(),
    ]
    assert case_file.mock_calls == calls
    reset_mocks()

    # -- no commands in the files
    case_file.return_value.exists.side_effect = [True, True]
    case_file.return_value.open.return_value.read.side_effect = [
        json.dumps({}),
        json.dumps({}),
    ]

    result = tested.summarized_generated_commands()
    assert result == []

    calls = [
        call("parameters2command.json"),
        call().exists(),
        call().open('r'),
        call().open().read(),
        call("staged_questionnaires.json"),
        call().exists(),
        call().open('r'),
        call().open().read(),
    ]
    assert case_file.mock_calls == calls
    reset_mocks()

    # -- commands only in common commands
    case_file.return_value.exists.side_effect = [True, True]
    case_file.return_value.open.return_value.read.side_effect = [
        json.dumps({
            "cycle_000": {
                "instructions": [
                    {"uuid": "uuid1", "information": "theInformation1"},
                ],
                "commands": [
                    {
                        "module": "theModule1",
                        "class": "TheClass1",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "attributeX": "valueX",
                            "attributeY": "valueY",
                        },
                    },
                ]},
            "cycle_001": {
                "instructions": [
                    {"uuid": "uuid1", "information": "theInformation2"},
                    {"uuid": "uuid3", "information": "theInformation3"},
                ],
                "commands": [
                    {
                        "module": "theModule2",
                        "class": "TheClass2",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "attributeZ": "valueZ",
                        },
                    },
                    {
                        "module": "theModule3",
                        "class": "TheClass3",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                        },
                    },
                ]},
            "cycle_002": {
                "instructions": [
                    {"uuid": "uuid4", "information": "theInformation4"},
                ],
                "commands": [
                    {
                        "module": "theModule4",
                        "class": "TheClass4",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "attributeA": "valueA",
                            "attributeB": "valueB",
                            "attributeC": "valueC",
                        },
                    },
                ]},
        }),
        json.dumps({}),
    ]

    result = tested.summarized_generated_commands()
    expected = [
        # -- theInformation1 is replaced with theInformation2....
        {
            "command": {
                "attributes": {
                    "attributeZ": "valueZ",
                },
                "class": "TheClass2",
                "module": "theModule2",
            },
            "instruction": "theInformation2",
        },
        {
            "command": {
                "attributes": {},
                "class": "TheClass3",
                "module": "theModule3",
            },
            "instruction": "theInformation3",
        },
        {
            "command": {
                "attributes": {
                    "attributeA": "valueA",
                    "attributeB": "valueB",
                    "attributeC": "valueC",
                },
                "class": "TheClass4",
                "module": "theModule4",
            },
            "instruction": "theInformation4",
        },
    ]
    assert result == expected

    assert case_file.mock_calls == calls
    reset_mocks()

    # -- commands only in questionnaire commands
    questionnaires = [
        {
            "name": "theQuestionnaire1",
            "dbid": 3,
            "questions": [
                {
                    "dbid": 9,
                    "label": "theRadioQuestion",
                    "type": "SING",
                    "skipped": None,
                    "responses": [
                        {"dbid": 25, "value": "Radio1", "selected": False, "comment": None},
                        {"dbid": 26, "value": "Radio2", "selected": False, "comment": None},
                        {"dbid": 27, "value": "Radio3", "selected": False, "comment": None},
                    ],
                },
                {
                    "dbid": 12,
                    "label": "theIntegerQuestion",
                    "type": "INT",
                    "skipped": None,
                    "responses": [
                        {"dbid": 41, "value": "", "selected": False, "comment": None},
                    ],
                }
            ]
        },
        {
            "name": "theQuestionnaire2",
            "dbid": 3,
            "questions": [
                {
                    "dbid": 10,
                    "label": "theCheckBoxQuestion",
                    "type": "MULT",
                    "skipped": None,
                    "responses": [
                        {"dbid": 33, "value": "Checkbox1", "selected": False, "comment": ""},
                        {"dbid": 34, "value": "Checkbox2", "selected": False, "comment": ""},
                        {"dbid": 35, "value": "Checkbox3", "selected": False, "comment": ""},
                    ]
                },
                {
                    "dbid": 11,
                    "label": "theTextQuestion",
                    "type": "TXT",
                    "skipped": None,
                    "responses": [
                        {"dbid": 37, "value": "", "selected": False, "comment": None},
                    ]
                },
                {
                    "dbid": 17,
                    "label": "otherTextQuestion",
                    "type": "TXT",
                    "skipped": None,
                    "responses": [
                        {"dbid": 51, "value": "", "selected": False, "comment": None},
                    ]
                },
            ]
        }
    ]
    case_file.return_value.exists.side_effect = [True, True]
    case_file.return_value.open.return_value.read.side_effect = [
        json.dumps({}),
        json.dumps({
            "cycle_000": {
                "instructions": [
                    {"uuid": "uuid1", "instruction": "questionnaireA", "information": json.dumps(questionnaires[0])},
                    {"uuid": "uuid2", "instruction": "questionnaireB", "information": json.dumps(questionnaires[1])},
                ],
                "commands": [
                    {
                        "module": "theModule1",
                        "class": "TheClass1",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "questions": {
                                "question-9": 999,
                                "question-12": 999,

                            },
                        },
                    },
                    {
                        "module": "theModule2",
                        "class": "TheClass2",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "questions": {
                                "question-10": [
                                    {
                                        "text": "Checkbox1",
                                        "value": 999,
                                        "comment": "",
                                        "selected": False,
                                    },
                                    {
                                        "text": "Checkbox2",
                                        "value": 999,
                                        "comment": "theComment2",
                                        "selected": True,
                                    },
                                    {
                                        "text": "Checkbox3",
                                        "value": 999,
                                        "comment": "",
                                        "selected": True,
                                    },
                                ],
                                "question-11": "theFreeText",
                            },
                        },
                    },
                ]},
            "cycle_002": {
                "instructions": [
                    {"uuid": "uuid1", "instruction": "questionnaireA", "information": json.dumps(questionnaires[0])},
                    {"uuid": "uuid2", "instruction": "questionnaireB", "information": json.dumps(questionnaires[1])},
                ],
                "commands": [
                    {
                        "module": "theModule1",
                        "class": "TheClass1",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "questions": {
                                "question-9": 26,
                                "question-12": 57,

                            },
                        },
                    },
                    {
                        "module": "theModule2",
                        "class": "TheClass2",
                        "attributes": {
                            "command_uuid": ">?<",
                            "note_uuid": ">?<",
                            "questions": {
                                "question-10": [
                                    {
                                        "text": "Checkbox1",
                                        "value": 33,
                                        "comment": "",
                                        "selected": False,
                                    },
                                    {
                                        "text": "Checkbox2",
                                        "value": 34,
                                        "comment": "theComment2",
                                        "selected": True,
                                    },
                                    {
                                        "text": "Checkbox3",
                                        "value": 35,
                                        "comment": "",
                                        "selected": True,
                                    },
                                ],
                                "question-11": "theFreeText",
                            },
                        },
                    },
                ]},
        }),
    ]

    result = tested.summarized_generated_commands()
    expected = [
        {
            'instruction': 'questionnaireA: theQuestionnaire1',
            'command': {
                'attributes': {
                    'theIntegerQuestion': 57,
                    'theRadioQuestion': 'Radio2',
                },
                'class': 'TheClass1',
                'module': 'theModule1',
            },
        },
        {
            'instruction': 'questionnaireB: theQuestionnaire2',
            'command': {
                'attributes': {
                    'theCheckBoxQuestion': 'Checkbox2 (theComment2), Checkbox3',
                    'theTextQuestion': 'theFreeText',
                },
                'class': 'TheClass2',
                'module': 'theModule2',
            },
        },
    ]

    assert result == expected

    assert case_file.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, "summarized_generated_commands")
@patch.object(AuditorFile, "case_file")
def test_generate_commands_summary(case_file, summarized_generated_commands):
    summary_initial = MagicMock()
    summary_revised = MagicMock()

    def reset_mocks():
        case_file.reset_mock()
        summarized_generated_commands.reset_mock()
        summary_initial.reset_mock()
        summary_revised.reset_mock()

    tested = AuditorFile("theCase", 7)

    # the revised file does not exist yet
    buffers = [
        MockFile(),
        MockFile(),
    ]
    summarized_generated_commands.side_effect = [{"key": "data"}]
    case_file.side_effect = [summary_initial, summary_revised]
    summary_initial.open.side_effect = [buffers[0]]
    summary_revised.open.side_effect = [buffers[1]]
    summary_revised.exists.side_effect = [False]

    result = tested.generate_commands_summary()
    assert result is summary_initial

    expected = {"key": "data"}
    assert buffers[0].content == json.dumps(expected, indent=2)
    assert buffers[1].content == json.dumps(expected, indent=2)

    calls = [
        call('summary_initial.json'),
        call('summary_revised.json'),
    ]
    assert case_file.mock_calls == calls
    calls = [call()]
    assert summarized_generated_commands.mock_calls == calls
    calls = [call.open('w')]
    assert summary_initial.mock_calls == calls
    calls = [
        call.exists(),
        call.open('w'),
    ]
    assert summary_revised.mock_calls == calls
    reset_mocks()

    # the revised file already exists
    buffers = [
        MockFile(),
        MockFile(json.dumps({"key": "other"}, indent=2)),
    ]
    summarized_generated_commands.side_effect = [{"key": "data"}]
    case_file.side_effect = [summary_initial, summary_revised]
    summary_initial.open.side_effect = [buffers[0]]
    summary_revised.open.side_effect = [buffers[1]]
    summary_revised.exists.side_effect = [True]

    result = tested.generate_commands_summary()
    assert result is summary_initial

    expected = {"key": "data"}
    assert buffers[0].content == json.dumps(expected, indent=2)
    expected = {"key": "other"}
    assert buffers[1].content == json.dumps(expected, indent=2)

    calls = [
        call('summary_initial.json'),
        call('summary_revised.json'),
    ]
    assert case_file.mock_calls == calls
    calls = [call()]
    assert summarized_generated_commands.mock_calls == calls
    calls = [call.open('w')]
    assert summary_initial.mock_calls == calls
    calls = [call.exists()]
    assert summary_revised.mock_calls == calls
    reset_mocks()


@patch("evaluations.auditor_file.Path")
@patch.object(AuditorFile, "case_file")
@patch.object(AuditorFile, "is_complete")
def test_generate_html_summary(is_complete, case_file, path):
    template_file = MagicMock()
    data_file = MagicMock()
    html_file = MagicMock()

    def reset_mocks():
        is_complete.reset_mock()
        case_file.reset_mock()
        template_file.reset_mock()
        data_file.reset_mock()
        html_file.reset_mock()

    tested = AuditorFile("theCase", 7)

    # the case has been completed
    buffers = [
        MockFile("HTML: case {{theCase}}, data: {{theData}}."),
        MockFile(json.dumps({"key": "other"}, indent=2)),
        MockFile(),
    ]
    is_complete.side_effect = [True]
    path.return_value.parent.__truediv__.side_effect = [template_file]
    case_file.side_effect = [data_file, html_file]

    template_file.open.side_effect = [buffers[0]]
    data_file.open.side_effect = [buffers[1]]
    html_file.open.side_effect = [buffers[2]]

    result = tested.generate_html_summary()
    assert result is html_file

    expected = 'HTML: case theCase, data: {\n  "key": "other"\n}.'
    assert buffers[2].content == expected
    expected = json.dumps({"key": "other"}, indent=2)
    assert buffers[1].content == expected
    expected = "HTML: case {{theCase}}, data: {{theData}}."
    assert buffers[0].content == expected

    calls = [call()]
    assert is_complete.mock_calls == calls
    calls = [
        call("summary_revised.json"),
        call("summary.html"),
    ]
    assert case_file.mock_calls == calls
    calls = [call.open('r')]
    assert template_file.mock_calls == calls
    calls = [call.open('w')]
    assert html_file.mock_calls == calls
    calls = [call.open('r')]
    assert data_file.mock_calls == calls
    reset_mocks()

    # the case is not completed

    is_complete.side_effect = [False]
    path.return_value.parent.__truediv__.side_effect = []
    case_file.side_effect = []

    result = tested.generate_html_summary()
    assert result is None

    calls = [call()]
    assert is_complete.mock_calls == calls
    assert case_file.mock_calls == []
    assert template_file.mock_calls == []
    assert html_file.mock_calls == []
    assert data_file.mock_calls == []
    reset_mocks()
