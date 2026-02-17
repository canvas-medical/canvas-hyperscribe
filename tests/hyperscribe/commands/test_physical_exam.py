import hashlib
from unittest.mock import MagicMock, patch

import pytest
from canvas_sdk.commands import PhysicalExamCommand

from hyperscribe.commands.base_questionnaire import BaseQuestionnaire
from hyperscribe.commands.physical_exam import PhysicalExam
from hyperscribe.libraries.limited_cache import LimitedCache
from hyperscribe.structures.access_policy import AccessPolicy
from hyperscribe.structures.identification_parameters import IdentificationParameters
from hyperscribe.structures.instruction_with_parameters import InstructionWithParameters
from hyperscribe.structures.question import Question
from hyperscribe.structures.question_type import QuestionType
from hyperscribe.structures.questionnaire import Questionnaire
from hyperscribe.structures.response import Response
from hyperscribe.structures.settings import Settings
from hyperscribe.structures.vendor_key import VendorKey


def helper_instance() -> PhysicalExam:
    settings = Settings(
        llm_text=VendorKey(vendor="textVendor", api_key="textKey"),
        llm_audio=VendorKey(vendor="audioVendor", api_key="audioKey"),
        structured_rfv=False,
        audit_llm=False,
        reasoning_llm=False,
        custom_prompts=[],
        is_tuning=False,
        api_signing_key="theApiSigningKey",
        max_workers=3,
        hierarchical_detection_threshold=5,
        send_progress=False,
        commands_policy=AccessPolicy(policy=False, items=[]),
        staffers_policy=AccessPolicy(policy=False, items=[]),
        trial_staffers_policy=AccessPolicy(policy=True, items=[]),
        cycle_transcript_overlap=37,
    )
    cache = LimitedCache("patientUuid", "providerUuid", {})
    identification = IdentificationParameters(
        patient_uuid="patientUuid",
        note_uuid="noteUuid",
        provider_uuid="providerUuid",
        canvas_instance="canvasInstance",
    )
    return PhysicalExam(settings, cache, identification)


def test_class():
    tested = PhysicalExam
    assert issubclass(tested, BaseQuestionnaire)


def test_schema_key():
    tested = PhysicalExam
    result = tested.schema_key()
    expected = "exam"
    assert result == expected


def test_command_from_json():
    chatter = MagicMock()
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        instruction = InstructionWithParameters(
            uuid="theUuid",
            index=7,
            instruction="theInstruction",
            information="theInformation",
            is_new=False,
            is_updated=True,
            previous_information="thePreviousInformation",
            parameters={"key": "value"},
        )
        _ = tested.command_from_json(instruction, chatter)
    assert chatter.mock_calls == []


def test_command_parameters():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.command_parameters()


def test_instruction_description():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.instruction_description()


def test_instruction_constraints():
    tested = helper_instance()
    with pytest.raises(NotImplementedError):
        _ = tested.instruction_constraints()


def test_include_skipped():
    tested = helper_instance()
    result = tested.include_skipped()
    assert result is True


def test_additional_instructions():
    tested = helper_instance()
    result = tested.additional_instructions()
    assert len(result) == 2
    assert hashlib.md5(result[0].encode()).hexdigest() == "fa17394ae4790665d519c04150ba4dfb"
    assert hashlib.md5(result[1].encode()).hexdigest() == "c55d9ae3fe7886276774f1b585335ee0"


def test_skipped_field_instruction():
    tested = helper_instance()
    result = tested.skipped_field_instruction()
    assert "CRITICAL" in result
    assert "Never change 'skipped' from 'false' back to 'true' or 'null'" in result
    assert (
        hashlib.md5(result.encode()).hexdigest()
        == hashlib.md5(
            (
                "CRITICAL: If a question already has 'skipped' set to 'false', you MUST keep it as 'false'. "
                "Never change 'skipped' from 'false' back to 'true' or 'null'. "
                "You may only change 'skipped' from 'true' to 'false' if the question is clearly addressed "
                "in the transcript. Body systems that are already enabled must stay enabled."
            ).encode()
        ).hexdigest()
    )


@patch("hyperscribe.commands.physical_exam.log")
def test_post_process_questionnaire_preserves_enabled_state(mock_log):
    """LLM flips skipped from False to True — post-process reverts it."""
    tested = helper_instance()
    original = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=100, value="normal", selected=False, comment=None)],
            ),
            Question(
                dbid=11,
                label="HEENT",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=101, value="clear", selected=False, comment=None)],
            ),
        ],
    )
    updated = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=[Response(dbid=100, value="normal", selected=False, comment=None)],
            ),
            Question(
                dbid=11,
                label="HEENT",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=101, value="updated findings", selected=False, comment=None)],
            ),
        ],
    )
    result = tested.post_process_questionnaire(original, updated)
    # General: skipped reverted from True back to False (original was False)
    assert result.questions[0].skipped is False
    assert result.questions[0].responses[0].value == "normal"
    # HEENT: stayed False, text updated normally
    assert result.questions[1].skipped is False
    assert result.questions[1].responses[0].value == "updated findings"
    assert mock_log.info.mock_calls != []


@patch("hyperscribe.commands.physical_exam.log")
def test_post_process_questionnaire_normalizes_none_to_false(mock_log):
    """Skipped=None should be normalized to False (enabled by default)."""
    tested = helper_instance()
    original = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=None,
                responses=[Response(dbid=100, value="", selected=False, comment=None)],
            ),
        ],
    )
    updated = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=None,
                responses=[Response(dbid=100, value="", selected=False, comment=None)],
            ),
        ],
    )
    result = tested.post_process_questionnaire(original, updated)
    assert result.questions[0].skipped is False
    assert mock_log.info.mock_calls == []


@patch("hyperscribe.commands.physical_exam.log")
def test_post_process_questionnaire_preserves_text(mock_log):
    """LLM clears existing text — post-process restores it."""
    tested = helper_instance()
    original = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=100, value="normal appearance", selected=False, comment=None)],
            ),
        ],
    )
    updated = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=100, value="", selected=False, comment=None)],
            ),
        ],
    )
    result = tested.post_process_questionnaire(original, updated)
    assert result.questions[0].responses[0].value == "normal appearance"
    assert mock_log.info.mock_calls != []


@patch("hyperscribe.commands.physical_exam.log")
def test_post_process_questionnaire_allows_text_updates(mock_log):
    """LLM updates text with new content — post-process allows it."""
    tested = helper_instance()
    original = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=100, value="normal", selected=False, comment=None)],
            ),
        ],
    )
    updated = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=100, value="well-appearing, no distress", selected=False, comment=None)],
            ),
        ],
    )
    result = tested.post_process_questionnaire(original, updated)
    assert result.questions[0].responses[0].value == "well-appearing, no distress"
    assert mock_log.info.mock_calls == []


@patch("hyperscribe.commands.physical_exam.log")
def test_post_process_questionnaire_allows_skipped_true_to_false(mock_log):
    """LLM enables a previously-skipped question — post-process allows it."""
    tested = helper_instance()
    original = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=True,
                responses=[Response(dbid=100, value="", selected=False, comment=None)],
            ),
        ],
    )
    updated = Questionnaire(
        dbid=1,
        name="PE",
        questions=[
            Question(
                dbid=10,
                label="General",
                type=QuestionType.TYPE_TEXT,
                skipped=False,
                responses=[Response(dbid=100, value="new findings", selected=False, comment=None)],
            ),
        ],
    )
    result = tested.post_process_questionnaire(original, updated)
    assert result.questions[0].skipped is False
    assert result.questions[0].responses[0].value == "new findings"
    assert mock_log.info.mock_calls == []


@patch("hyperscribe.commands.physical_exam.log")
def test_post_process_questionnaire_unknown_question(mock_log):
    """Updated questionnaire has a question not in original — passes through."""
    tested = helper_instance()
    original = Questionnaire(
        dbid=1,
        name="PE",
        questions=[],
    )
    new_q = Question(
        dbid=99,
        label="Unknown",
        type=QuestionType.TYPE_TEXT,
        skipped=True,
        responses=[Response(dbid=999, value="text", selected=False, comment=None)],
    )
    updated = Questionnaire(
        dbid=1,
        name="PE",
        questions=[new_q],
    )
    result = tested.post_process_questionnaire(original, updated)
    assert result.questions[0] is new_q
    assert mock_log.info.mock_calls == []


def test_sdk_command():
    tested = helper_instance()
    result = tested.sdk_command()
    expected = PhysicalExamCommand
    assert result == expected
