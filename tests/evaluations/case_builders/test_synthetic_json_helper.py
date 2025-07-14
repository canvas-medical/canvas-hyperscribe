import json, sys, pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.case_builders.helper_synthetic_json import generate_json

@patch("evaluations.case_builders.synthetic_json_helper.LlmOpenaiO3")
def test_generate_json_success(mock_llm_cls, tmp_path):
    expected = {"key": "value"}
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.response = json.dumps(expected)

    mock_llm.request.return_value = mock_response
    mock_llm_cls.return_value = mock_llm

    tested = generate_json(
        vendor_key=VendorKey("openai", "dummy_key"),
        system_prompt=["System prompt"],
        user_prompt=["User prompt"],
        schema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
        retries=2
    )

    assert tested == expected
    mock_llm.set_system_prompt.assert_called_once_with(["System prompt"])
    mock_llm.set_user_prompt.assert_called_once_with(["User prompt"])
    assert mock_llm.request.call_count == 1

@patch("evaluations.case_builders.synthetic_json_helper.LlmOpenaiO3")
def test_generate_json_invalid_json_then_valid(mock_llm_cls, tmp_path):
    expected = {"key": "final_value"}

    first_response = MagicMock()
    first_response.response = "{ invalid json"

    second_response = MagicMock()
    second_response.response = json.dumps(expected)

    mock_llm = MagicMock()
    mock_llm.request.side_effect = [first_response, second_response]
    mock_llm_cls.return_value = mock_llm

    tested = generate_json(
        vendor_key=VendorKey("openai", "retry_key"),
        system_prompt=["sys"],
        user_prompt=["user"],
        schema={"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]},
        retries=2)

    assert tested == expected
    assert mock_llm.request.call_count == 2
    mock_llm.set_system_prompt.assert_called()
    mock_llm.set_user_prompt.assert_called()

@patch("evaluations.case_builders.synthetic_json_helper.LlmOpenaiO3")
def test_generate_json_validation_error_then_success(mock_llm_cls):
    invalid = {"bad_key": 123}
    valid = {"key": "good"}

    first_response = MagicMock()
    first_response.response = json.dumps(invalid)

    second_response = MagicMock()
    second_response.response = json.dumps(valid)

    mock_llm = MagicMock()
    mock_llm.request.side_effect = [first_response, second_response]
    mock_llm_cls.return_value = mock_llm

    schema = {
        "type": "object",
        "properties": {"key": {"type": "string"}},
        "required": ["key"]}

    tested = generate_json(
        vendor_key=VendorKey("openai", "retry_val"),
        system_prompt=["sys"],
        user_prompt=["user"],
        schema=schema,
        retries=2)

    assert tested == valid
    assert mock_llm.request.call_count == 2
    mock_llm.set_system_prompt.assert_called()
    mock_llm.set_user_prompt.assert_called()

@patch("evaluations.case_builders.synthetic_json_helper.LlmOpenaiO3")
def test_generate_json_fails_and_writes_file(mock_llm_cls, tmp_path):
    mock_llm = MagicMock()
    mock_response = MagicMock()
    mock_response.response = "{not_valid_json"
    mock_llm.request.return_value = mock_response
    mock_llm_cls.return_value = mock_llm

    # Redirect the invalid_output.json to tmp_path
    invalid_file = tmp_path / "invalid_output.json"

    # Patch Path to point to tmp_path
    with patch("evaluations.case_builders.synthetic_json_helper.Path", return_value=invalid_file):
        with pytest.raises(SystemExit) as exc:
            generate_json(
                vendor_key=VendorKey("openai", "fail_key"),
                system_prompt=["sys"],
                user_prompt=["user"],
                schema={"type": "object", "properties": {"x": {"type": "string"}}, "required": ["x"]},
                retries=2
            )

    assert exc.value.code == 1
    assert invalid_file.exists()
    contents = invalid_file.read_text()
    assert "not_valid_json" in contents