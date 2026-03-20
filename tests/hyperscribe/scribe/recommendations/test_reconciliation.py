import json
from http import HTTPStatus
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from hyperscribe.scribe.recommendations.reconciliation import reconcile_sections


def _mock_llm_response(sections: list[dict[str, Any]]) -> SimpleNamespace:
    return SimpleNamespace(
        code=HTTPStatus.OK,
        response=json.dumps({"sections": sections}),
    )


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_sections_success(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client

    mock_client.request.return_value = _mock_llm_response(
        [
            {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever.", "updated": False},
            {"key": "eyes", "title": "EYES", "text": "Blurred vision noted.", "updated": True},
        ]
    )

    template = [
        {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever."},
        {"key": "eyes", "title": "EYES", "text": "Denies visual changes."},
    ]
    encounter = [
        {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "No fever."},
        {"key": "eyes", "title": "EYES", "text": "Blurred vision noted."},
    ]

    result = reconcile_sections(template, encounter, "test-key", "Review of Systems")
    assert result is not None
    assert len(result) == 2
    assert result[0]["updated"] is False
    assert result[0]["template_text"] == "Denies fever."
    assert result[1]["updated"] is True
    assert result[1]["text"] == "Blurred vision noted."
    assert result[1]["template_text"] == "Denies visual changes."

    mock_client.set_system_prompt.assert_called_once()
    mock_client.set_user_prompt.assert_called_once()
    mock_client.set_schema.assert_called_once()


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_sections_new_system_has_no_template_text(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client

    mock_client.request.return_value = _mock_llm_response(
        [
            {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever.", "updated": False},
            {"key": "respiratory", "title": "RESPIRATORY", "text": "Mild wheezing.", "updated": True},
        ]
    )

    template = [{"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever."}]
    encounter = [
        {"key": "constitutional", "title": "CONSTITUTIONAL", "text": "Denies fever."},
        {"key": "respiratory", "title": "RESPIRATORY", "text": "Mild wheezing."},
    ]

    result = reconcile_sections(template, encounter, "test-key", "ROS")
    assert result is not None
    assert result[1]["updated"] is True
    assert result[1]["template_text"] is None  # New system, no template original


def test_reconcile_sections_empty_template() -> None:
    result = reconcile_sections([], [{"key": "a", "title": "A", "text": "text"}], "key", "ROS")
    assert result is None


def test_reconcile_sections_empty_encounter() -> None:
    result = reconcile_sections([{"key": "a", "title": "A", "text": "text"}], [], "key", "ROS")
    assert result is None


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_sections_llm_failure_returns_none(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.side_effect = Exception("timeout")

    template = [{"key": "a", "title": "A", "text": "text"}]
    encounter = [{"key": "a", "title": "A", "text": "other"}]
    result = reconcile_sections(template, encounter, "key", "ROS")
    assert result is None


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_sections_non_ok_returns_none(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = SimpleNamespace(code=HTTPStatus.BAD_REQUEST, response="")

    template = [{"key": "a", "title": "A", "text": "text"}]
    encounter = [{"key": "a", "title": "A", "text": "other"}]
    result = reconcile_sections(template, encounter, "key", "ROS")
    assert result is None


@patch("hyperscribe.scribe.recommendations.reconciliation.LlmAnthropic")
def test_reconcile_sections_malformed_json_returns_none(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = SimpleNamespace(code=HTTPStatus.OK, response="not json")

    template = [{"key": "a", "title": "A", "text": "text"}]
    encounter = [{"key": "a", "title": "A", "text": "other"}]
    result = reconcile_sections(template, encounter, "key", "ROS")
    assert result is None
