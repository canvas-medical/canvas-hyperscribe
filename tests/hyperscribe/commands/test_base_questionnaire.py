import json
from unittest.mock import call, MagicMock, patch

import pytest
from canvas_sdk.commands.commands.questionnaire import QuestionnaireCommand
from canvas_sdk.commands.commands.questionnaire.toggle_questions import ToggleQuestionsMixin

from hyperscribe.commands.base import Base
from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.coded_item import CodedItem
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction import Instruction
from hyperscribe.structures.line import Line
from hyperscribe.structures.question import Question
from hyperscribe.structures.question_type import QuestionType
from hyperscribe.structures.questionnaire import Questionnaire
from hyperscribe.structures.response import Response
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> BaseQuestionnaire:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        science_host="scienceHost",
        ontologies_host="ontologiesHost",
        pre_shared_key="preSharedKey",
        structured_rfv=False,
        audit_llm=False,
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return BaseQuestionnaire(settings, cache, identification)


def test_class():
    tested = BaseQuestionnaire
    assert issubclass(tested, Base)


def test_include_skipped():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.include_skipped()


def test_staged_command_extract():
    tested = BaseQuestionnaire
    tests = [
        ({}, None),
        (
            {
                "skip-60": True,
                "skip-61": False,
                "skip-62": True,
                "skip-63": True,
                "question-60": [
                    {"text": "option1", "comment": "", "selected": False},
                    {"text": "option2", "comment": "comment2", "selected": True},
                    {"text": "option3", "comment": "", "selected": True},
                    {"text": "option4", "comment": "comment4", "selected": False},
                ],
                "question-61": 183,
                "question-62": "theResponse62",
                "question-63": 777,
                "question-64": [
                    {"text": "option10", "comment": "comment10", "selected": False},
                    {"text": "option11", "comment": "", "selected": False},
                    {
                        "text": "option12",
                        "comment": "",
                        "selected": False,
                    },  # <-- this additional option should never happen
                ],
                "questionnaire": {
                    "extra": {
                        "pk": 123,
                        "name": "theQuestionnaire",
                        "questions": [
                            {
                                "pk": 60,
                                "name": "question-60",
                                "type": "MULT",
                                "label": "theQuestion1",
                                "options": [
                                    {"pk": 177, "label": "option1"},
                                    {"pk": 179, "label": "option2"},
                                    {"pk": 180, "label": "option3"},
                                    {"pk": 181, "label": "option4"},
                                ],
                            },
                            {
                                "pk": 61,
                                "name": "question-61",
                                "type": "SING",
                                "label": "theQuestion2",
                                "options": [
                                    {"pk": 182, "label": "option5"},
                                    {"pk": 183, "label": "option6"},
                                    {"pk": 187, "label": "option7"},
                                ],
                            },
                            {
                                "pk": 62,
                                "name": "question-62",
                                "type": "TXT",
                                "label": "theQuestion3",
                                "options": [{"pk": 191, "label": "option8"}],
                            },
                            {
                                "pk": 63,
                                "name": "question-63",
                                "type": "INT",
                                "label": "theQuestion4",
                                "options": [{"pk": 192, "label": "option9"}],
                            },
                            {
                                "pk": 64,
                                "name": "question-64",
                                "type": "MULT",
                                "label": "theQuestion5",
                                "options": [{"pk": 193, "label": "option10"}, {"pk": 197, "label": "option11"}],
                            },
                            {
                                "pk": 65,
                                "name": "question-65",
                                "type": "TXT",
                                "label": "theQuestion6",
                                "options": [{"pk": 201, "label": "option12"}],
                            },
                        ],
                    },
                },
            },
            {
                "name": "theQuestionnaire",
                "dbid": 123,
                "questions": [
                    {
                        "dbid": 60,
                        "label": "theQuestion1",
                        "type": "MULT",
                        "skipped": False,
                        "responses": [
                            {"dbid": 177, "value": "option1", "selected": False, "comment": ""},
                            {"dbid": 179, "value": "option2", "selected": True, "comment": "comment2"},
                            {"dbid": 180, "value": "option3", "selected": True, "comment": ""},
                            {"dbid": 181, "value": "option4", "selected": False, "comment": "comment4"},
                        ],
                    },
                    {
                        "dbid": 61,
                        "label": "theQuestion2",
                        "type": "SING",
                        "skipped": True,
                        "responses": [
                            {"dbid": 182, "value": "option5", "selected": False, "comment": None},
                            {"dbid": 183, "value": "option6", "selected": True, "comment": None},
                            {"dbid": 187, "value": "option7", "selected": False, "comment": None},
                        ],
                    },
                    {
                        "dbid": 62,
                        "label": "theQuestion3",
                        "type": "TXT",
                        "skipped": False,
                        "responses": [{"dbid": 191, "value": "theResponse62", "selected": False, "comment": None}],
                    },
                    {
                        "dbid": 63,
                        "label": "theQuestion4",
                        "type": "INT",
                        "skipped": False,
                        "responses": [{"dbid": 192, "value": 777, "selected": False, "comment": None}],
                    },
                    {
                        "dbid": 64,
                        "label": "theQuestion5",
                        "type": "MULT",
                        "skipped": None,
                        "responses": [
                            {"dbid": 193, "value": "option10", "selected": False, "comment": "comment10"},
                            {"dbid": 197, "value": "option11", "selected": False, "comment": ""},
                        ],
                    },
                    {
                        "dbid": 65,
                        "label": "theQuestion6",
                        "type": "TXT",
                        "skipped": None,
                        "responses": [{"dbid": 201, "value": "", "selected": False, "comment": None}],
                    },
                ],
            },
        ),
    ]
    for data, expected in tests:
        result = tested.staged_command_extract(data)
        if expected is None:
            assert result is None
        else:
            assert isinstance(result, CodedItem)
            assert result.code == ""
            assert result.uuid == ""
            assert json.loads(result.label) == expected


def test_json_schema():
    tested = BaseQuestionnaire
    result = tested.json_schema(True)
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "items": {
            "properties": {
                "question": {"type": "string"},
                "questionId": {"type": "integer"},
                "questionType": {
                    "enum": ["free text", "integer", "single choice", "multiple choice"],
                    "type": "string",
                },
                "responses": {
                    "items": {
                        "properties": {
                            "responseId": {"type": "integer"},
                            "selected": {"type": "boolean"},
                            "value": {"type": "string"},
                            "comment": {
                                "description": "any relevant information expanding the answer",
                                "type": "string",
                            },
                        },
                        "required": ["responseId", "value", "selected"],
                        "type": "object",
                    },
                    "type": "array",
                },
                "skipped": {
                    "type": ["boolean", "null"],
                    "description": "indicates if the question is skipped or used",
                },
            },
            "required": ["questionId", "question", "questionType", "responses", "skipped"],
            "type": "object",
        },
        "type": "array",
    }
    assert result == expected
    #
    result = tested.json_schema(False)
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "items": {
            "properties": {
                "question": {"type": "string"},
                "questionId": {"type": "integer"},
                "questionType": {
                    "enum": ["free text", "integer", "single choice", "multiple choice"],
                    "type": "string",
                },
                "responses": {
                    "items": {
                        "properties": {
                            "responseId": {"type": "integer"},
                            "selected": {"type": "boolean"},
                            "value": {"type": "string"},
                            "comment": {
                                "description": "any relevant information expanding the answer",
                                "type": "string",
                            },
                        },
                        "required": ["responseId", "value", "selected"],
                        "type": "object",
                    },
                    "type": "array",
                },
            },
            "required": ["questionId", "question", "questionType", "responses"],
            "type": "object",
        },
        "type": "array",
    }
    assert result == expected


@patch.object(BaseQuestionnaire, "include_skipped")
def test_update_from_transcript(include_skipped):
    mock_chatter = MagicMock()

    def reset_mocks():
        include_skipped.reset_mock()
        mock_chatter.reset_mock()

    discussion = Line.load_from_json(
        [
            {"speaker": "spk1", "text": "line1"},
            {"speaker": "spk2", "text": "line2"},
            {"speaker": "spk2", "text": "line3"},
            {"speaker": "spk1", "text": "line4"},
        ],
    )
    questionnaire = Questionnaire(
        dbid=123,
        name="theQuestionnaire",
        questions=[
            Question(
                dbid=234,
                label="theQuestion1",
                type=QuestionType.TYPE_RADIO,
                skipped=False,
                responses=[
                    Response(dbid=142, value="theResponse1", selected=True, comment=None),
                    Response(dbid=143, value="theResponse2", selected=False, comment=None),
                ],
            ),
            Question(
                dbid=345,
                label="theQuestion2",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=[Response(dbid=144, value="theResponse3", selected=True, comment=None)],
            ),
            Question(
                dbid=369,
                label="theQuestion3",
                type=QuestionType.TYPE_INTEGER,
                skipped=True,
                responses=[Response(dbid=145, value=444, selected=True, comment=None)],
            ),
            Question(
                dbid=371,
                label="theQuestion4",
                type=QuestionType.TYPE_CHECKBOX,
                skipped=False,
                responses=[
                    Response(dbid=146, value="theResponse5", selected=True, comment="theComment5"),
                    Response(dbid=147, value="theResponse6", selected=True, comment="theComment6"),
                    Response(dbid=148, value="theResponse7", selected=False, comment="theComment7"),
                ],
            ),
        ],
    )

    system_prompt = [
        "The conversation is in the context of a clinical encounter between patient and licensed healthcare provider.",
        "The healthcare provider is editing a questionnaire 'theQuestionnaire', potentially without notifying "
        "the patient to prevent biased answers.",
        "The user will submit two JSON Markdown blocks:",
        "- the current state of the questionnaire,",
        "- a partial transcript of the visit of a patient with the healthcare provider.",
        "",
        "Your task is to identifying from the transcript which questions the healthcare provider is referencing "
        "and what responses the patient is giving.",
        "Since this is only a part of the transcript, it may have no reference to the questionnaire at all.",
        "",
        "Your response must be the JSON Markdown block of the questionnaire, with all the necessary changes "
        "to reflect the transcript content.",
        "",
    ]

    user_prompts = {
        "withSkipped": [
            "Below is a part of the transcript between the patient and the healthcare provider:",
            "```json",
            "[\n "
            '{\n  "speaker": "spk1",\n  "text": "line1"\n },\n '
            '{\n  "speaker": "spk2",\n  "text": "line2"\n },\n '
            '{\n  "speaker": "spk2",\n  "text": "line3"\n },\n '
            '{\n  "speaker": "spk1",\n  "text": "line4"\n }\n]',
            "```",
            "",
            "The questionnaire 'theQuestionnaire' is currently as follow,:",
            "```json",
            "[{"
            '"questionId": 234, '
            '"question": "theQuestion1", '
            '"questionType": "single choice", '
            '"responses": ['
            '{"responseId": 142, "value": "theResponse1", "selected": true}, '
            '{"responseId": 143, "value": "theResponse2", "selected": false}], '
            '"skipped": false}, '
            "{"
            '"questionId": 345, '
            '"question": "theQuestion2", '
            '"questionType": "free text", '
            '"responses": [{"responseId": 144, "value": "theResponse3", "selected": true}], '
            '"skipped": true}, '
            "{"
            '"questionId": 369, '
            '"question": "theQuestion3", '
            '"questionType": "integer", '
            '"responses": [{"responseId": 145, "value": 444, "selected": true}], '
            '"skipped": true}, '
            "{"
            '"questionId": 371, '
            '"question": "theQuestion4", '
            '"questionType": "multiple choice", '
            '"responses": ['
            '{"responseId": 146, '
            '"value": "theResponse5", '
            '"selected": true, '
            '"comment": "theComment5", '
            '"description": "add in the comment key any relevant information expanding the answer"}, '
            '{"responseId": 147, '
            '"value": "theResponse6", '
            '"selected": true, '
            '"comment": "theComment6", '
            '"description": "add in the comment key any relevant information expanding the answer"}, '
            '{"responseId": 148, '
            '"value": "theResponse7", '
            '"selected": false, '
            '"comment": "theComment7", '
            '"description": "add in the comment key any relevant information expanding the answer"}], '
            '"skipped": false}]',
            "```",
            "",
            "Your task is to replace the values of the JSON object as necessary.",
            "Since the current questionnaire's state is based on previous parts of the transcript, the changes "
            "should be based on explicit information only.",
            "This includes the values of 'skipped', change it to 'false' only if the question "
            "is obviously answered in the transcript, don't change it at all otherwise.",
            "",
        ],
        "noSkipped": [
            "Below is a part of the transcript between the patient and the healthcare provider:",
            "```json",
            "[\n "
            '{\n  "speaker": "spk1",\n  "text": "line1"\n },\n '
            '{\n  "speaker": "spk2",\n  "text": "line2"\n },\n '
            '{\n  "speaker": "spk2",\n  "text": "line3"\n },\n '
            '{\n  "speaker": "spk1",\n  "text": "line4"\n }\n]',
            "```",
            "",
            "The questionnaire 'theQuestionnaire' is currently as follow,:",
            "```json",
            "[{"
            '"questionId": 234, '
            '"question": "theQuestion1", '
            '"questionType": "single choice", '
            '"responses": ['
            '{"responseId": 142, "value": "theResponse1", "selected": true}, '
            '{"responseId": 143, "value": "theResponse2", "selected": false}]}, '
            "{"
            '"questionId": 345, '
            '"question": "theQuestion2", '
            '"questionType": "free text", '
            '"responses": [{"responseId": 144, "value": "theResponse3", "selected": true}]}, '
            "{"
            '"questionId": 369, '
            '"question": "theQuestion3", '
            '"questionType": "integer", '
            '"responses": [{"responseId": 145, "value": 444, "selected": true}]}, '
            "{"
            '"questionId": 371, '
            '"question": "theQuestion4", '
            '"questionType": "multiple choice", '
            '"responses": ['
            '{"responseId": 146, '
            '"value": "theResponse5", '
            '"selected": true, '
            '"comment": "theComment5", '
            '"description": "add in the comment key any relevant information expanding the answer"}, '
            '{"responseId": 147, '
            '"value": "theResponse6", '
            '"selected": true, '
            '"comment": "theComment6", '
            '"description": "add in the comment key any relevant information expanding the answer"}, '
            '{"responseId": 148, '
            '"value": "theResponse7", '
            '"selected": false, '
            '"comment": "theComment7", '
            '"description": "add in the comment key any relevant information expanding the answer"}]}]',
            "```",
            "",
            "Your task is to replace the values of the JSON object as necessary.",
            "Since the current questionnaire's state is based on previous parts of the transcript, the changes "
            "should be based on explicit information only.",
            "",
        ],
    }
    schemas = {
        "withSkipped": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "questionId": {"type": "integer"},
                    "question": {"type": "string"},
                    "questionType": {
                        "type": "string",
                        "enum": ["free text", "integer", "single choice", "multiple choice"],
                    },
                    "responses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "responseId": {"type": "integer"},
                                "value": {"type": "string"},
                                "selected": {"type": "boolean"},
                                "comment": {
                                    "type": "string",
                                    "description": "any relevant information expanding the answer",
                                },
                            },
                            "required": ["responseId", "value", "selected"],
                        },
                    },
                    "skipped": {
                        "type": ["boolean", "null"],
                        "description": "indicates if the question is skipped or used",
                    },
                },
                "required": ["questionId", "question", "questionType", "responses", "skipped"],
            },
        },
        "noSkipped": {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "questionId": {"type": "integer"},
                    "question": {"type": "string"},
                    "questionType": {
                        "type": "string",
                        "enum": ["free text", "integer", "single choice", "multiple choice"],
                    },
                    "responses": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "responseId": {"type": "integer"},
                                "value": {"type": "string"},
                                "selected": {"type": "boolean"},
                                "comment": {
                                    "type": "string",
                                    "description": "any relevant information expanding the answer",
                                },
                            },
                            "required": ["responseId", "value", "selected"],
                        },
                    },
                },
                "required": ["questionId", "question", "questionType", "responses"],
            },
        },
    }

    tested = helper_instance()
    tests = [
        (True, "withSkipped"),
        (False, "noSkipped"),
    ]
    for side_include_skipped, key_skipped in tests:
        # get a response
        include_skipped.side_effect = [side_include_skipped]
        mock_chatter.single_conversation.side_effect = [
            [
                {
                    "question": "theQuestion1",
                    "questionId": 234,
                    "questionType": "single choice",
                    "responses": [
                        {"responseId": 142, "selected": True, "value": "theResponse1"},
                        {"responseId": 143, "selected": False, "value": "theResponse2"},
                    ],
                    "skipped": False,
                },
                {
                    "question": "theQuestion2",
                    "questionId": 345,
                    "questionType": "free text",
                    "responses": [{"responseId": 144, "selected": True, "value": "theResponse3"}],
                    "skipped": True,
                },
                {
                    "question": "theQuestion3",
                    "questionId": 369,
                    "questionType": "integer",
                    "responses": [{"responseId": 145, "selected": True, "value": 444}],
                    "skipped": True,
                },
                {
                    "question": "theQuestion4",
                    "questionId": 371,
                    "questionType": "multiple choice",
                    "responses": [
                        {"responseId": 146, "selected": True, "value": "theResponse5", "comment": "theComment5"},
                        {"responseId": 147, "selected": True, "value": "theResponse6", "comment": "theComment6"},
                        {"responseId": 148, "selected": False, "value": "theResponse7", "comment": "theComment7"},
                    ],
                    "skipped": False,
                },
            ],
        ]
        instruction = Instruction(
            uuid="theUuid",
            index=0,
            instruction="theInstruction",
            information=json.dumps(questionnaire.to_json()),
            is_new=False,
            is_updated=True,
        )

        result = tested.update_from_transcript(discussion, instruction, mock_chatter)
        assert result == questionnaire
        calls = [call()]
        assert include_skipped.mock_calls == calls
        calls = [
            call.single_conversation(
                system_prompt,
                user_prompts[key_skipped],
                [schemas[key_skipped]],
                instruction,
            )
        ]
        assert mock_chatter.mock_calls == calls
        reset_mocks()

        # no response
        include_skipped.side_effect = [side_include_skipped]
        mock_chatter.single_conversation.side_effect = [None]
        result = tested.update_from_transcript(discussion, instruction, mock_chatter)
        assert result is None
        calls = [call()]
        assert include_skipped.mock_calls == calls
        calls = [
            call.single_conversation(
                system_prompt,
                user_prompts[key_skipped],
                [schemas[key_skipped]],
                instruction,
            )
        ]
        assert mock_chatter.mock_calls == calls
        reset_mocks()

        # invalid question definition
        instruction = Instruction(
            uuid="theUuid",
            index=0,
            instruction="theInstruction",
            information="something",
            is_new=False,
            is_updated=True,
        )
        include_skipped.side_effect = []
        mock_chatter.single_conversation.side_effect = []
        result = tested.update_from_transcript(discussion, instruction, mock_chatter)
        assert result is None
        assert include_skipped.mock_calls == []
        assert mock_chatter.mock_calls == []
        reset_mocks()


@patch.object(ToggleQuestionsMixin, "set_question_enabled")
@patch.object(BaseQuestionnaire, "include_skipped")
@patch.object(BaseQuestionnaire, "sdk_command")
def test_command_from_questionnaire(sdk_command, include_skipped, set_question_enabled):
    def reset_mocks():
        sdk_command.reset_mock()
        include_skipped.reset_mock()
        set_question_enabled.reset_mock()

    tested = helper_instance()

    questionnaire = Questionnaire(
        dbid=123,
        name="theQuestionnaire",
        questions=[
            Question(
                dbid=234,
                label="theQuestion1",
                type=QuestionType.TYPE_RADIO,
                skipped=False,
                responses=[
                    Response(dbid=142, value="theResponse1", selected=False, comment=None),
                    Response(dbid=143, value="theResponse2", selected=True, comment=None),
                ],
            ),
            Question(
                dbid=125,
                label="theQuestion3",
                type=QuestionType.TYPE_CHECKBOX,
                skipped=True,
                responses=[
                    Response(dbid=145, value="theResponse4", selected=False, comment="theComment4"),
                    Response(dbid=146, value="theResponse5", selected=True, comment=""),
                    Response(dbid=147, value="theResponse6", selected=True, comment="theComment6"),
                    Response(dbid=148, value="theResponse7", selected=False, comment="theComment7"),
                ],
            ),
            Question(
                dbid=345,
                label="theQuestion2",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=144, value="changedResponse3", selected=True, comment=None)],
            ),
            Question(
                dbid=236,
                label="theQuestion4",
                type=QuestionType.TYPE_INTEGER,
                skipped=False,
                responses=[Response(dbid=144, value=777, selected=True, comment=None)],
            ),
        ],
    )

    class TestQuestionnaireCommand(ToggleQuestionsMixin, QuestionnaireCommand):
        pass

    tests = [
        (True, [call("234", True), call("125", False), call("345", True), call("236", True)]),
        (False, []),
    ]

    for side_effect_skipped, exp_calls_enabled in tests:
        sdk_command.side_effect = [TestQuestionnaireCommand]
        include_skipped.side_effect = [side_effect_skipped]

        result = tested.command_from_questionnaire("theUuid", questionnaire)

        assert isinstance(result, TestQuestionnaireCommand)
        assert result.command_uuid == "theUuid"
        assert result.note_uuid == "noteUuid"
        assert len(result.questions) == 4
        assert result.questions[0].response == 143
        assert result.questions[1].response == [
            {"text": "theResponse4", "value": 145, "comment": "theComment4", "selected": False},
            {"text": "theResponse5", "value": 146, "comment": "", "selected": True},
            {"text": "theResponse6", "value": 147, "comment": "theComment6", "selected": True},
            {"text": "theResponse7", "value": 148, "comment": "theComment7", "selected": False},
        ]
        assert result.questions[2].response == "changedResponse3"
        assert result.questions[3].response == 777

        calls = [call()]
        assert sdk_command.mock_calls == calls
        calls = [call()]
        assert include_skipped.mock_calls == calls
        assert set_question_enabled.mock_calls == exp_calls_enabled
        reset_mocks()


def test_is_available():
    tested = helper_instance()
    result = tested.is_available()
    assert result is True
