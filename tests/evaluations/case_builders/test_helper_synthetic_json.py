import json, pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson

def _invalid_path(tmp_path: Path) -> Path:
    # Helper to capture the real Path("invalid_output.json") in tmp_path 
    return tmp_path / "invalid_output.json"

@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate__json_success(mock_llm_cls, tmp_path):
    expected = {"key": "value"}
    mock_result = MagicMock()
    mock_result.has_error = False
    mock_result.content = [expected]
    mock_llm = MagicMock()
    mock_llm.chat.return_value = mock_result
    mock_llm_cls.return_value = mock_llm

    tested = HelperSyntheticJson.generate_json(
        vendor_key=VendorKey("openai", "dummy_key"),
        system_prompt=["System prompt"],
        user_prompt=["User prompt"],
        schema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},)

    assert tested == expected
    assert not (tmp_path / "invalid_output.json").exists()

@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate_json__parses_fenced_json(mock_llm_cls, tmp_path):
    expected = {"foo": 123}
    mock_result = MagicMock(has_error=False, content=[expected])
    mock_llm = MagicMock()
    mock_llm.chat.return_value = mock_result
    mock_llm_cls.return_value = mock_llm

    got = HelperSyntheticJson.generate_json(
        vendor_key=VendorKey("openai", "dummy"),
        system_prompt=["sys"],
        user_prompt=["user"],
        schema={
            "type": "object",
            "properties": {"foo": {"type": "number"}},
            "required": ["foo"]
        },
    )
    assert got == expected

@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate_json__schema_validation_failure_exits(mock_llm_cls, tmp_path):
    bad = {"not_key": "oops"}
    mock_result = MagicMock(has_error=False, content=[bad])
    mock_llm = MagicMock()
    mock_llm.chat.return_value = mock_result
    mock_llm_cls.return_value   = mock_llm

    # capture Path(...) in tmp_path
    invalid = _invalid_path(tmp_path)
    with patch("evaluations.case_builders.helper_synthetic_json.Path", return_value=invalid):
        with pytest.raises(SystemExit):
            HelperSyntheticJson.generate_json(
                vendor_key=VendorKey("openai", "dummy"),
                system_prompt=["sys"],
                user_prompt=["user"],
                schema={
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"]
                },
            )

    # invalid_output.json should contain the raw content
    assert invalid.exists()
    assert json.dumps(bad) in invalid.read_text()

@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate_json__chat_error_exits(mock_llm_cls, tmp_path):
    # LLM.chat signals a lower-level error
    mock_result = MagicMock(has_error=True, content="irrelevant", error="network fail")
    mock_llm = MagicMock()
    mock_llm.chat.return_value = mock_result
    mock_llm_cls.return_value   = mock_llm

    invalid = _invalid_path(tmp_path)
    with patch("evaluations.case_builders.helper_synthetic_json.Path", return_value=invalid):
        with pytest.raises(SystemExit):
            HelperSyntheticJson.generate_json(
                vendor_key=VendorKey("openai", "dummy"),
                system_prompt=["sys"],
                user_prompt=["user"],
                schema={
                    "type": "object",
                    "properties": {"key": {"type": "string"}},
                    "required": ["key"]
                },
            )

    #invalid_output.json should contain the error string
    assert invalid.exists()
    assert "network fail" in invalid.read_text()