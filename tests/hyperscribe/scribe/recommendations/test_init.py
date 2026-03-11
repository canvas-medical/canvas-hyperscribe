from __future__ import annotations

from unittest.mock import MagicMock, patch

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection
from hyperscribe.scribe.recommendations import recommend_commands


def _make_note() -> ClinicalNote:
    return ClinicalNote(
        title="Test Note",
        sections=[
            NoteSection(key="current_medications", title="Current Medications", text="- Lisinopril 10mg daily"),
            NoteSection(key="allergies", title="Allergies", text="Penicillin (rash)"),
        ],
    )


@patch("hyperscribe.scribe.recommendations.LlmAnthropic")
def test_recommend_commands_calls_all_recommenders(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client

    med_proposal = CommandProposal(
        command_type="medication_statement",
        display="Lisinopril 10mg",
        data={"medication_text": "Lisinopril 10mg"},
        section_key="_recommended",
    )
    allergy_proposal = CommandProposal(
        command_type="allergy",
        display="Penicillin",
        data={"allergy_text": "Penicillin"},
        section_key="_recommended",
    )

    with (
        patch(
            "hyperscribe.scribe.recommendations.MedicationRecommender.recommend",
            return_value=[med_proposal],
        ) as mock_med,
        patch(
            "hyperscribe.scribe.recommendations.AllergyRecommender.recommend",
            return_value=[allergy_proposal],
        ) as mock_allergy,
    ):
        note = _make_note()
        proposals = recommend_commands(note, "test-api-key")

    assert len(proposals) == 2
    assert proposals[0].command_type == "medication_statement"
    assert proposals[1].command_type == "allergy"
    mock_med.assert_called_once_with(note, mock_client)
    mock_allergy.assert_called_once_with(note, mock_client)


@patch("hyperscribe.scribe.recommendations.LlmAnthropic")
def test_recommend_commands_creates_client_with_settings(mock_llm_cls: MagicMock) -> None:
    mock_llm_cls.return_value = MagicMock()

    with (
        patch("hyperscribe.scribe.recommendations.MedicationRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.AllergyRecommender.recommend", return_value=[]),
    ):
        recommend_commands(_make_note(), "my-api-key")

    mock_llm_cls.assert_called_once()
    settings = mock_llm_cls.call_args.args[0]
    assert settings.api_key == "my-api-key"
    assert settings.temperature == 0.0
    assert settings.max_tokens == 4096


@patch("hyperscribe.scribe.recommendations.LlmAnthropic")
def test_recommend_commands_handles_recommender_exception(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client

    allergy_proposal = CommandProposal(
        command_type="allergy",
        display="Penicillin",
        data={"allergy_text": "Penicillin"},
        section_key="_recommended",
    )

    with (
        patch(
            "hyperscribe.scribe.recommendations.MedicationRecommender.recommend",
            side_effect=Exception("Unexpected error"),
        ),
        patch(
            "hyperscribe.scribe.recommendations.AllergyRecommender.recommend",
            return_value=[allergy_proposal],
        ),
    ):
        proposals = recommend_commands(_make_note(), "test-api-key")

    # Medication recommender failed but allergy recommender still returns results
    assert len(proposals) == 1
    assert proposals[0].command_type == "allergy"


@patch("hyperscribe.scribe.recommendations.LlmAnthropic")
def test_recommend_commands_empty_note(mock_llm_cls: MagicMock) -> None:
    mock_llm_cls.return_value = MagicMock()

    with (
        patch("hyperscribe.scribe.recommendations.MedicationRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.AllergyRecommender.recommend", return_value=[]),
    ):
        note = ClinicalNote(title="Empty", sections=[])
        proposals = recommend_commands(note, "test-api-key")

    assert proposals == []
