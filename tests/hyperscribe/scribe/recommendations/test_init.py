from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from hyperscribe.scribe.backend.models import ClinicalNote, CommandProposal, NoteSection
from hyperscribe.scribe.recommendations import prescription_dispense_enabled, recommend_commands


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

    rx_proposal = CommandProposal(
        command_type="prescribe",
        display="Sumatriptan 50mg",
        data={"fdb_code": "99999", "medication_text": "Sumatriptan 50mg"},
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
        patch(
            "hyperscribe.scribe.recommendations.PrescriptionRecommender.recommend",
            return_value=[rx_proposal],
        ) as mock_rx,
        patch("hyperscribe.scribe.recommendations.ReferRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.TaskRecommender.recommend", return_value=[]),
    ):
        note = _make_note()
        proposals = recommend_commands(note, "test-api-key")

    assert len(proposals) == 3
    assert proposals[0].command_type == "medication_statement"
    assert proposals[1].command_type == "allergy"
    assert proposals[2].command_type == "prescribe"
    mock_med.assert_called_once_with(note, mock_client, transcript=None)
    mock_allergy.assert_called_once_with(note, mock_client, transcript=None)
    mock_rx.assert_called_once_with(note, mock_client, transcript=None)


@patch("hyperscribe.scribe.recommendations.LlmAnthropic")
def test_recommend_commands_creates_client_with_settings(mock_llm_cls: MagicMock) -> None:
    mock_llm_cls.return_value = MagicMock()

    with (
        patch("hyperscribe.scribe.recommendations.MedicationRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.AllergyRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.PrescriptionRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.ReferRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.TaskRecommender.recommend", return_value=[]),
    ):
        recommend_commands(_make_note(), "my-api-key")

    # Each recommender gets its own client instance
    assert mock_llm_cls.call_count == 5
    for call in mock_llm_cls.call_args_list:
        settings = call.args[0]
        assert settings.api_key == "my-api-key"
        assert settings.temperature == 0.0
        assert settings.max_tokens == 4096


@patch("hyperscribe.scribe.recommendations.LlmAnthropic")
def test_recommend_commands_handles_recommender_exception(mock_llm_cls: MagicMock) -> None:
    mock_llm_cls.return_value = MagicMock()

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
        patch(
            "hyperscribe.scribe.recommendations.PrescriptionRecommender.recommend",
            return_value=[],
        ),
        patch("hyperscribe.scribe.recommendations.ReferRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.TaskRecommender.recommend", return_value=[]),
    ):
        proposals = recommend_commands(_make_note(), "test-api-key")

    # Medication recommender failed but allergy recommender still returns results
    assert len(proposals) == 1
    assert proposals[0].command_type == "allergy"


@pytest.mark.parametrize(
    "allowlist, provider_id, expected",
    [
        (None, "abc", True),  # unset -> all users (fail-open)
        ("", "abc", True),  # blank -> all
        ("   ", "abc", True),  # whitespace-only -> all
        ("abc", "abc", True),  # listed
        ("abc, def", "def", True),  # listed (comma + space tokenized)
        ("abc,def", "xyz", False),  # not listed
        ("abc", None, False),  # non-blank list but no provider -> off
        ("abc", "ABC", False),  # exact match (case-sensitive), consistent with other staffer secrets
    ],
)
def test_prescription_dispense_enabled(allowlist: str | None, provider_id: str | None, expected: bool) -> None:
    assert prescription_dispense_enabled(allowlist, provider_id) is expected


@patch("hyperscribe.scribe.recommendations.LlmAnthropic")
@patch("hyperscribe.scribe.recommendations.PrescriptionRecommender")
def test_recommend_commands_threads_dispense_flag(mock_rx_cls: MagicMock, mock_llm_cls: MagicMock) -> None:
    mock_llm_cls.return_value = MagicMock()
    mock_rx_cls.return_value.recommend.return_value = []
    with (
        patch("hyperscribe.scribe.recommendations.MedicationRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.AllergyRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.ReferRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.TaskRecommender.recommend", return_value=[]),
    ):
        recommend_commands(_make_note(), "k", dispense_engine_enabled=False)
    mock_rx_cls.assert_called_once_with(dispense_engine_enabled=False)


@patch("hyperscribe.scribe.recommendations.LlmAnthropic")
def test_recommend_commands_empty_note(mock_llm_cls: MagicMock) -> None:
    mock_llm_cls.return_value = MagicMock()

    with (
        patch("hyperscribe.scribe.recommendations.MedicationRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.AllergyRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.PrescriptionRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.ReferRecommender.recommend", return_value=[]),
        patch("hyperscribe.scribe.recommendations.TaskRecommender.recommend", return_value=[]),
    ):
        note = ClinicalNote(title="Empty", sections=[])
        proposals = recommend_commands(note, "test-api-key")

    assert proposals == []
