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
from hyperscribe.structures.questionnaire import Questionnaire as QuestionnaireDefinition
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


def test_sdk_command():
    tested = helper_instance()
    result = tested.sdk_command()
    expected = PhysicalExamCommand
    assert result == expected


def _make_question(dbid: int, label: str, text: str, skipped: bool | None = False) -> Question:
    return Question(
        dbid=dbid,
        label=label,
        type=QuestionType.TYPE_TEXT,
        skipped=skipped,
        responses=[Response(dbid=dbid * 10, value=text, selected=True, comment=None)],
    )


def _make_questionnaire(questions: list[Question]) -> QuestionnaireDefinition:
    return QuestionnaireDefinition(dbid=1, name="Comprehensive Physical Exam", questions=questions)


class TestPostProcessQuestionnaire:
    def test_preserves_text_when_llm_clears_it(self):
        """LLM returns empty text for a body system that had default findings — keep the original."""
        tested = helper_instance()
        original = _make_questionnaire(
            [
                _make_question(387, "General", "NAD. Well-developed, pleasant."),
                _make_question(388, "HEENT", "PERRL. EOMI. TMs clear."),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(387, "General", "Patient comfortable, non-antalgic gait."),
                _make_question(388, "HEENT", ""),  # LLM cleared this
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].responses[0].value == "Patient comfortable, non-antalgic gait."
        assert result.questions[1].responses[0].value == "PERRL. EOMI. TMs clear."

    def test_preserves_skipped_false(self):
        """LLM flips skipped from False to True — keep it False."""
        tested = helper_instance()
        original = _make_questionnaire(
            [
                _make_question(390, "Respiratory", "CTA bilaterally.", skipped=False),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(390, "Respiratory", "CTA bilaterally.", skipped=True),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].skipped is False

    def test_allows_skipped_true_to_false(self):
        """LLM enables a previously skipped system — allow it."""
        tested = helper_instance()
        original = _make_questionnaire(
            [
                _make_question(393, "Lymphatic", "", skipped=True),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(393, "Lymphatic", "No lymphadenopathy.", skipped=False),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].skipped is False
        assert result.questions[0].responses[0].value == "No lymphadenopathy."

    def test_allows_text_replacement(self):
        """LLM replaces existing text with new findings — allow it."""
        tested = helper_instance()
        original = _make_questionnaire(
            [
                _make_question(394, "Musculoskeletal", "Normal ROM all extremities."),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(394, "Musculoskeletal", "Mild tenderness at L5-S1. ROM limited."),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].responses[0].value == "Mild tenderness at L5-S1. ROM limited."

    def test_preserves_text_when_llm_returns_whitespace(self):
        """LLM returns whitespace-only text — treat as empty, keep original."""
        tested = helper_instance()
        original = _make_questionnaire(
            [
                _make_question(391, "Cardiovascular", "RRR. No murmurs."),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(391, "Cardiovascular", "   "),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].responses[0].value == "RRR. No murmurs."

    def test_normalizes_skipped_none_to_false(self):
        """skipped=None should become False for PE — body systems are enabled by default."""
        tested = helper_instance()
        original = _make_questionnaire(
            [
                _make_question(390, "Respiratory", "CTA bilaterally.", skipped=None),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(390, "Respiratory", "CTA bilaterally.", skipped=None),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].skipped is False

    @patch.object(PhysicalExam, "get_template_framework")
    def test_fills_sub_default_when_both_empty(self, mock_get_framework):
        """Both original and updated are empty — fill from {sub:} template default."""
        tested = helper_instance()
        mock_get_framework.return_value = (
            "{sub:PERRL. EOMI. TMs clear bilaterally.}{add:Replace with transcript findings if available.}"
        )
        original = _make_questionnaire(
            [
                _make_question(388, "HEENT", ""),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(388, "HEENT", ""),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].responses[0].value == "PERRL. EOMI. TMs clear bilaterally."
        mock_get_framework.assert_called_with("HEENT")

    @patch.object(PhysicalExam, "get_template_framework")
    def test_no_lit_default_leaves_empty(self, mock_get_framework):
        """Both empty and no template framework — stays empty."""
        tested = helper_instance()
        mock_get_framework.return_value = None
        original = _make_questionnaire(
            [
                _make_question(393, "Lymphatic", ""),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(393, "Lymphatic", ""),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].responses[0].value == ""

    @patch.object(PhysicalExam, "get_template_framework")
    def test_fills_lit_default_when_both_empty(self, mock_get_framework):
        """Both original and updated are empty — {lit:} also works as fallback."""
        tested = helper_instance()
        mock_get_framework.return_value = "{lit:CTA bilaterally. No wheezes.}"
        original = _make_questionnaire(
            [
                _make_question(390, "Respiratory", ""),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(390, "Respiratory", ""),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].responses[0].value == "CTA bilaterally. No wheezes."

    @patch.object(PhysicalExam, "get_template_framework")
    def test_template_default_not_used_when_llm_provides_text(self, mock_get_framework):
        """LLM provides text — use it, don't fall back to template default."""
        tested = helper_instance()
        mock_get_framework.return_value = "{sub:Default findings.}"
        original = _make_questionnaire(
            [
                _make_question(387, "General", ""),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(387, "General", "Patient appears comfortable."),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].responses[0].value == "Patient appears comfortable."

    def test_prevents_null_to_true_transition(self):
        """LLM flips skipped from None to True — keep it enabled (normalize to False)."""
        tested = helper_instance()
        original = _make_questionnaire(
            [
                _make_question(392, "Abdomen", "Soft, non-tender.", skipped=None),
            ]
        )
        updated = _make_questionnaire(
            [
                _make_question(392, "Abdomen", "Soft, non-tender.", skipped=True),
            ]
        )

        result = tested.post_process_questionnaire(original, updated)

        assert result.questions[0].skipped is False
