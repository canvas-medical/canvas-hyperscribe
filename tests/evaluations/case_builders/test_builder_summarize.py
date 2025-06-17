import json
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, call

from evaluations.auditor_file import AuditorFile
from evaluations.case_builders.builder_summarize import BuilderSummarize


@patch("evaluations.case_builders.builder_summarize.ArgumentParser")
def test_parameters(argument_parser):
    def reset_mocks():
        argument_parser.reset_mock()

    tested = BuilderSummarize

    argument_parser.return_value.parse_args.side_effect = ["parse_args called"]
    result = tested._parameters()
    expected = "parse_args called"
    assert result == expected

    calls = [
        call(description="Generate a single document with all instructions and generated commands"),
        call().add_argument("--summarize", action="store_true"),
        call().add_argument("--case", type=str, required=True, help="Evaluation case"),
        call().parse_args(),
    ]
    assert argument_parser.mock_calls == calls
    reset_mocks()


@patch("evaluations.case_builders.builder_summarize.NamedTemporaryFile")
@patch("evaluations.case_builders.builder_summarize.Path")
@patch("evaluations.case_builders.builder_summarize.browser_open")
@patch.object(BuilderSummarize, "summary_generated_commands")
@patch.object(BuilderSummarize, "_parameters")
def test_run(parameters, summary_generated_commands, browser_open, path, named_temporary_file):
    def reset_mocks():
        parameters.reset_mock()
        summary_generated_commands.reset_mock()
        browser_open.reset_mock()
        path.reset_mock()
        named_temporary_file.reset_mock()

    directory = Path(__file__).parent.as_posix().replace("/tests", "")

    tested = BuilderSummarize()
    parameters.side_effect = [Namespace(case="theCase")]
    summary_generated_commands.side_effect = [{"key": "value"}]
    path.return_value.parent.__truediv__.return_value.open.return_value.__enter__.return_value.read.side_effect = [
        "theTemplate with {{theCase}} and {{theData}} to display"]
    named_temporary_file.return_value.__enter__.return_value.name = "theNamedTemporaryFile"

    tested.run()

    calls = [call()]
    assert parameters.mock_calls == calls
    calls = [call("theCase")]
    assert summary_generated_commands.mock_calls == calls
    calls = [call('file://theNamedTemporaryFile')]
    assert browser_open.mock_calls == calls
    calls = [
        call(f'{directory}/builder_summarize.py'),
        call().parent.__truediv__('summary.html'),
        call().parent.__truediv__().open('r'),
        call().parent.__truediv__().open().__enter__(),
        call().parent.__truediv__().open().__enter__().read(),
        call().parent.__truediv__().open().__exit__(None, None, None)
    ]
    assert path.mock_calls == calls
    calls = [
        call(delete=False, suffix='.html', mode='w'),
        call().__enter__(),
        call().__enter__().write('theTemplate with theCase and {"key": "value"} to display'),
        call().__exit__(None, None, None)
    ]
    assert named_temporary_file.mock_calls == calls
    reset_mocks()


@patch.object(AuditorFile, "case_file_from")
def test_summary_generated_commands(case_file_from):

    def reset_mocks():
        case_file_from.reset_mock()

    tested = BuilderSummarize

    # there are no files for the case
    case_file_from.return_value.exists.side_effect = [False, False]

    result = tested.summary_generated_commands("theCase")
    assert result == []
    calls = [
        call("parameters2command", "json"),
        call().exists(),
        call("staged_questionnaires", "json"),
        call().exists(),
    ]
    assert case_file_from.mock_calls == calls
    reset_mocks()

    # -- no commands in the files
    case_file_from.return_value.exists.side_effect = [True, True]
    case_file_from.return_value.open.return_value.read.side_effect = [
        json.dumps({}),
        json.dumps({}),
    ]

    result = tested.summary_generated_commands("theCase")
    assert result == []

    calls = [
        call("parameters2command", "json"),
        call().exists(),
        call().open('r'),
        call().open().read(),
        call("staged_questionnaires", "json"),
        call().exists(),
        call().open('r'),
        call().open().read(),
    ]
    assert case_file_from.mock_calls == calls
    reset_mocks()

    # -- commands only in common commands
    case_file_from.return_value.exists.side_effect = [True, True]
    case_file_from.return_value.open.return_value.read.side_effect = [
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

    result = tested.summary_generated_commands("theCase")
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

    assert case_file_from.mock_calls == calls
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
    case_file_from.return_value.exists.side_effect = [True, True]
    case_file_from.return_value.open.return_value.read.side_effect = [
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

    result = tested.summary_generated_commands("theCase")
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

    assert case_file_from.mock_calls == calls
    reset_mocks()
