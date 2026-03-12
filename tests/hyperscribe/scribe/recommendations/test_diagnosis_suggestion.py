from __future__ import annotations

import json
from http import HTTPStatus
from unittest.mock import MagicMock, patch

from canvas_sdk.clients.llms.structures import LlmResponse, LlmTokens

from hyperscribe.scribe.recommendations.diagnosis_suggestion import (
    _validate_code,
    suggest_diagnoses,
)


def _make_science_response(results: list[dict[str, str]]) -> MagicMock:
    resp = MagicMock()
    resp.json.return_value = {"results": results}
    return resp


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.science_http")
def test_validate_code_found(mock_science: MagicMock) -> None:
    mock_science.get_json.return_value = _make_science_response(
        [{"icd10_code": "R519", "icd10_text": "Headache, unspecified", "score": 1.0}]
    )
    result = _validate_code("R519")
    assert result is not None
    assert result["code"] == "R519"
    assert result["display"] == "Headache, unspecified"
    assert result["formatted_code"] == "R51.9"


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.science_http")
def test_validate_code_not_found(mock_science: MagicMock) -> None:
    mock_science.get_json.return_value = _make_science_response(
        [{"icd10_code": "Z999", "icd10_text": "Something else", "score": 0.5}]
    )
    result = _validate_code("R519")
    assert result is None


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.science_http")
def test_validate_code_exception(mock_science: MagicMock) -> None:
    mock_science.get_json.side_effect = Exception("Network error")
    result = _validate_code("R519")
    assert result is None


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion._validate_code")
@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.LlmAnthropic")
def test_suggest_diagnoses_success(mock_llm_cls: MagicMock, mock_validate: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response=json.dumps(
            {
                "suggestions": [
                    {"conditionText": "Right-sided headache", "icd10Codes": ["R519", "G43909"]},
                ]
            }
        ),
        tokens=LlmTokens(prompt=100, generated=50),
    )

    mock_validate.side_effect = [
        {"code": "R519", "display": "Headache, unspecified", "formatted_code": "R51.9"},
        {"code": "G43909", "display": "Migraine, unspecified", "formatted_code": "G43.909"},
    ]

    result = suggest_diagnoses(["Right-sided headache"], "test-api-key")

    assert "Right-sided headache" in result
    assert len(result["Right-sided headache"]) == 2
    assert result["Right-sided headache"][0]["code"] == "R519"
    assert result["Right-sided headache"][1]["code"] == "G43909"


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion._validate_code")
@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.LlmAnthropic")
def test_suggest_diagnoses_code_not_validated(mock_llm_cls: MagicMock, mock_validate: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response=json.dumps(
            {
                "suggestions": [
                    {"conditionText": "Knee pain", "icd10Codes": ["M25561", "XXXXX"]},
                ]
            }
        ),
        tokens=LlmTokens(prompt=100, generated=50),
    )

    mock_validate.side_effect = [
        {"code": "M25561", "display": "Pain in right knee", "formatted_code": "M25.561"},
        None,  # second code doesn't validate
    ]

    result = suggest_diagnoses(["Knee pain"], "test-api-key")

    assert len(result["Knee pain"]) == 1
    assert result["Knee pain"][0]["code"] == "M25561"


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion._validate_code")
@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.LlmAnthropic")
def test_suggest_diagnoses_all_codes_invalid(mock_llm_cls: MagicMock, mock_validate: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response=json.dumps(
            {
                "suggestions": [
                    {"conditionText": "Unknown condition", "icd10Codes": ["XXXXX"]},
                ]
            }
        ),
        tokens=LlmTokens(prompt=100, generated=50),
    )
    mock_validate.return_value = None

    result = suggest_diagnoses(["Unknown condition"], "test-api-key")

    # Condition with no valid codes is omitted from the result.
    assert "Unknown condition" not in result


def test_suggest_diagnoses_empty_conditions() -> None:
    result = suggest_diagnoses([], "test-api-key")
    assert result == {}


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.LlmAnthropic")
def test_suggest_diagnoses_llm_error(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = LlmResponse(
        code=HTTPStatus.INTERNAL_SERVER_ERROR,
        response="Server error",
        tokens=LlmTokens(prompt=0, generated=0),
    )

    result = suggest_diagnoses(["Headache"], "test-api-key")
    assert result == {}


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.LlmAnthropic")
def test_suggest_diagnoses_llm_exception(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.side_effect = Exception("Network error")

    result = suggest_diagnoses(["Headache"], "test-api-key")
    assert result == {}


@patch("hyperscribe.scribe.recommendations.diagnosis_suggestion.LlmAnthropic")
def test_suggest_diagnoses_malformed_response(mock_llm_cls: MagicMock) -> None:
    mock_client = MagicMock()
    mock_llm_cls.return_value = mock_client
    mock_client.request.return_value = LlmResponse(
        code=HTTPStatus.OK,
        response="not valid json",
        tokens=LlmTokens(prompt=100, generated=50),
    )

    result = suggest_diagnoses(["Headache"], "test-api-key")
    assert result == {}
