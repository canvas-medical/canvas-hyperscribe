import json
from unittest.mock import patch, call, MagicMock

import pytest

from evaluations.auditor_store import AuditorStore
from hyperscribe.libraries.auditor import Auditor
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.instruction_with_command import InstructionWithCommand
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.line import Line


def test_class():
    tested = AuditorStore
    assert issubclass(tested, Auditor)


def test___init__():
    tests = [
        (-1, 0, "cycle_000"),
        (0, 0, "cycle_000"),
        (1, 1, "cycle_001"),
        (3, 3, "cycle_003"),
        (10, 10, "cycle_010"),
    ]
    for cycle, exp_cycle, exp_key in tests:
        tested = AuditorStore("theCase", cycle)
        assert tested.case == "theCase"
        assert tested.cycle == exp_cycle
        assert tested.cycle_key == exp_key


def test_upsert_audio():
    tested = AuditorStore("theCase", 3)
    with pytest.raises(NotImplementedError):
        _ = tested.upsert_audio("theLabel", b"some audio")


def test_upsert_json():
    tested = AuditorStore("theCase", 3)
    with pytest.raises(NotImplementedError):
        _ = tested.upsert_json("theLabel", {"key": "value"})


def test_get_json():
    tested = AuditorStore("theCase", 3)
    with pytest.raises(NotImplementedError):
        _ = tested.get_json("theLabel")


def test_finalize():
    tested = AuditorStore("theCase", 3)
    with pytest.raises(NotImplementedError):
        _ = tested.finalize(["error1", "error2"])


def test_set_cycle():
    tested = AuditorStore("theCase", 2)
    tests = [
        (-1, 2, "cycle_002"),
        (0, 2, "cycle_002"),
        (1, 2, "cycle_002"),
        (3, 3, "cycle_003"),
        (10, 10, "cycle_010"),
    ]
    for cycle, exp_cycle, exp_key in tests:
        tested.set_cycle(cycle)
        assert tested.cycle == exp_cycle
        assert tested.cycle_key == exp_key


@patch.object(AuditorStore, "upsert_audio")
@patch.object(AuditorStore, "upsert_json")
@patch.object(AuditorStore, "get_json")
def test_identified_transcript(get_json, upsert_json, upsert_audio):
    def reset_mocks():
        get_json.reset_mock()
        upsert_json.reset_mock()
        upsert_audio.reset_mock()

    tested = AuditorStore("theCase", 2)
    audios = [b"audio1", b"audio2", b"audio3"]
    transcript = [
        Line(speaker="speaker1", text="text1"),
        Line(speaker="speaker2", text="text2"),
        Line(speaker="speaker3", text="text3"),
        Line(speaker="speaker4", text="text4"),
    ]
    get_json.side_effect = [{"cycle_001": "data1", "cycle_002": "data2"}]

    result = tested.identified_transcript(audios, transcript)
    assert result is True

    calls = [call('audio2transcript')]
    assert get_json.mock_calls == calls
    calls = [
        call('audio2transcript', {
            'cycle_001': 'data1',
            'cycle_002': [
                {'speaker': 'speaker1', 'text': 'text1'},
                {'speaker': 'speaker2', 'text': 'text2'},
                {'speaker': 'speaker3', 'text': 'text3'},
                {'speaker': 'speaker4', 'text': 'text4'},
            ],
        }),
    ]
    assert upsert_json.mock_calls == calls
    calls = [
        call('cycle_002_00.mp3', b'audio1'),
        call('cycle_002_01.mp3', b'audio2'),
        call('cycle_002_02.mp3', b'audio3'),
    ]
    assert upsert_audio.mock_calls == calls
    reset_mocks()


@patch.object(AuditorStore, "upsert_json")
@patch.object(AuditorStore, "get_json")
def test_found_instructions(get_json, upsert_json):
    def reset_mocks():
        get_json.reset_mock()
        upsert_json.reset_mock()

    transcript = [
        Line(speaker="speaker1", text="text1"),
        Line(speaker="speaker2", text="text2"),
    ]
    initial = [
        Instruction(uuid="uuid1", index=0, instruction="theInstruction1", information="theInformation0", is_new=False, is_updated=False),
    ]
    cumulated = [
        Instruction(uuid="uuid1", index=0, instruction="theInstruction1", information="theInformation1", is_new=False, is_updated=True),
        Instruction(uuid="uuid2", index=1, instruction="theInstruction2", information="theInformation2", is_new=True, is_updated=False),
        Instruction(uuid="uuid3", index=2, instruction="theInstruction3", information="theInformation3", is_new=True, is_updated=False),
    ]
    get_json.side_effect = [{"cycle_001": "data1", "cycle_002": "data2"}]

    tested = AuditorStore("theCase", 2)
    result = tested.found_instructions(transcript, initial, cumulated)
    assert result is True

    calls = [call('transcript2instructions')]
    assert get_json.mock_calls == calls
    calls = [
        call('transcript2instructions', {
            'cycle_001': 'data1',
            'cycle_002': {
                'transcript': [
                    {'speaker': 'speaker1', 'text': 'text1'},
                    {'speaker': 'speaker2', 'text': 'text2'},
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
            },
        }),
    ]
    assert upsert_json.mock_calls == calls
    reset_mocks()


@patch.object(AuditorStore, "upsert_json")
@patch.object(AuditorStore, "get_json")
def test_computed_parameters(get_json, upsert_json):
    def reset_mocks():
        get_json.reset_mock()
        upsert_json.reset_mock()

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

    tests = [
        ({
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
         }, {
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
         }),
        ({}, {
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
        }),
    ]
    for previous_content, expected in tests:
        get_json.side_effect = [{"cycle_001": "data1"}]
        if previous_content:
            get_json.side_effect = [{
                "cycle_001": "data1",
                "cycle_002": previous_content,
            }]
        tested = AuditorStore("theCase", 2)
        result = tested.computed_parameters(sdk_parameters)
        assert result is True

        calls = [call('instruction2parameters')]
        assert get_json.mock_calls == calls
        calls = [
            call('instruction2parameters', {
                'cycle_001': 'data1',
                'cycle_002': expected,
            }),
        ]
        assert upsert_json.mock_calls == calls
        reset_mocks()


@patch.object(AuditorStore, "upsert_json")
@patch.object(AuditorStore, "get_json")
def test_computed_commands(get_json, upsert_json):
    commands = [MagicMock(), MagicMock()]

    def reset_mocks():
        get_json.reset_mock()
        upsert_json.reset_mock()
        for item in commands:
            item.reset_mock()

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

    tests = [
        ({}, {
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
        }),
        ({
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
         }, {
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
         }),
    ]

    for previous_content, expected in tests:
        get_json.side_effect = [{"cycle_001": "data1"}]
        if previous_content:
            get_json.side_effect = [{
                "cycle_001": "data1",
                "cycle_002": previous_content,
            }]
        tested = AuditorStore("theCase", 2)
        result = tested.computed_commands(sdk_parameters)
        assert result is True

        calls = [call('parameters2command')]
        assert get_json.mock_calls == calls
        calls = [
            call('parameters2command', {
                'cycle_001': 'data1',
                'cycle_002': expected,
            }),
        ]
        assert upsert_json.mock_calls == calls
        for cmd in commands:
            assert cmd.mock_calls == []
        reset_mocks()


@patch.object(AuditorStore, "upsert_json")
@patch.object(AuditorStore, "get_json")
def test_computed_questionnaires(get_json, upsert_json):
    commands = [MagicMock(), MagicMock(), MagicMock()]

    def reset_mocks():
        get_json.reset_mock()
        upsert_json.reset_mock()
        for item in commands:
            item.reset_mock()

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
    get_json.side_effect = [{
        "cycle_001": "data1",
        "cycle_002": "date2",
    }]
    tested = AuditorStore("theCase", 2)
    result = tested.computed_questionnaires(transcript, initial_instructions, instructions_with_command)
    assert result is True

    calls = [call('staged_questionnaires')]
    assert get_json.mock_calls == calls
    calls = [
        call('staged_questionnaires', {
            'cycle_001': 'data1',
            'cycle_002': {
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
        }),
    ]
    assert upsert_json.mock_calls == calls
    for cmd in commands:
        assert cmd.mock_calls == []
    reset_mocks()


@patch.object(AuditorStore, "get_json")
def test_summarized_generated_commands(get_json):
    def reset_mocks():
        get_json.reset_mock()

    tested = AuditorStore("theCase", 2)

    # -- no commands in the fields
    get_json.side_effect = [
        {},
        {},
    ]

    result = tested.summarized_generated_commands()
    assert result == []

    calls = [
        call("parameters2command"),
        call("staged_questionnaires"),
    ]
    assert get_json.mock_calls == calls
    reset_mocks()

    # -- commands only in common commands
    get_json.side_effect = [
        {
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
        },
        {},
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

    assert get_json.mock_calls == calls
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
    get_json.side_effect = [
        {},
        {
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
        },
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

    assert get_json.mock_calls == calls
    reset_mocks()


@patch.object(AuditorStore, "get_json")
def test_summarized_generated_commands_as_instructions(get_json):
    def reset_mocks():
        get_json.reset_mock()

    tested = AuditorStore("theCase", 2)

    # -- no commands in the fields
    get_json.side_effect = [
        {},
        {},
    ]

    result = tested.summarized_generated_commands_as_instructions()
    assert result == []

    calls = [
        call("parameters2command"),
        call("staged_questionnaires"),
    ]
    assert get_json.mock_calls == calls
    reset_mocks()

    # -- commands only in common commands
    get_json.side_effect = [
        {
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
        },
        {},
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

    assert get_json.mock_calls == calls
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
    get_json.side_effect = [
        {},
        {
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
        },
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

    assert get_json.mock_calls == calls
    reset_mocks()
