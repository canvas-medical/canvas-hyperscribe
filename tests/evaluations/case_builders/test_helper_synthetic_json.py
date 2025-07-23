import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch, call
from argparse import Namespace
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson, MemoryLog

def _invalid_path(tmp_path: Path) -> Path:
    # Helper to capture the real Path("invalid_output.json") in tmp_path 
    return tmp_path / "invalid_output.json"

@patch("evaluations.case_builders.helper_synthetic_json.MemoryLog")
@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate__json_success(mock_llm_cls, mock_memory_log, tmp_path):
    expected = {"key": "value"}
    result_obj = Namespace(has_error=False, content=[expected], error="")
    
    mock_llm = MagicMock()
    mock_llm.chat.return_value = result_obj
    mock_llm_cls.return_value = mock_llm
    mock_memory_log.dev_null_instance.side_effect = ["MemoryLogInstance"]

    schema = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}
    tested = HelperSyntheticJson.generate_json(
        vendor_key=VendorKey("openai", "dummy_key"),
        system_prompt=["System prompt"],
        user_prompt=["User prompt"],
        schema=schema)

    assert tested == expected
    assert not (tmp_path / "invalid_output.json").exists()
    
    expected_calls = [
        call("MemoryLogInstance", "dummy_key", with_audit=False, temperature=1.0),
        call().set_system_prompt(["System prompt"]),
        call().set_user_prompt(["User prompt"]),
        call().chat(schemas=[schema]),
    ]
    assert mock_llm_cls.mock_calls == expected_calls
    assert mock_llm.chat.call_count == 1
    calls = [call.dev_null_instance()]
    assert mock_memory_log.mock_calls == calls

    assert result_obj.has_error is False
    assert result_obj.content == [expected]


@patch("evaluations.case_builders.helper_synthetic_json.MemoryLog")
@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate_json__parses_fenced_json(mock_llm_cls, mock_memory_log, tmp_path):
    expected = {"foo": 123}
    result_obj = Namespace(has_error=False, content=[expected], error="network fail")

    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [result_obj]
    mock_llm_cls.return_value = mock_llm
    mock_memory_log.dev_null_instance.side_effect = ["MemoryLogInstance"]
    schema = {"type": "object", "properties": {"foo": {"type": "number"}}, "required": ["foo"]}

    tested = HelperSyntheticJson.generate_json(
        vendor_key=VendorKey("openai", "dummy"),
        system_prompt=["system"],
        user_prompt=["user"],
        schema=schema)
    assert tested == expected

    expected_calls = [
        call("MemoryLogInstance", "dummy", with_audit=False, temperature=1.0),
        call().set_system_prompt(["system"]),
        call().set_user_prompt(["user"]),
        call().chat(schemas=[schema]),
    ]
    assert mock_llm_cls.mock_calls == expected_calls
    assert mock_llm.chat.call_count == 1
    calls = [call.dev_null_instance()]
    assert mock_memory_log.mock_calls == calls

    assert result_obj.has_error is False
    assert result_obj.content == [expected]

@patch("evaluations.case_builders.helper_synthetic_json.MemoryLog")
@patch("evaluations.case_builders.helper_synthetic_json.LlmOpenaiO3")
def test_generate_json__chat_error_exits(mock_llm_cls, mock_memory_log, tmp_path):
    # LLM.chat signals a lower-level error
    schema = {"type": "object", "properties": {"key": {"type": "string"}}, "required": ["key"]}
    tested_obj = Namespace(has_error=True, content="irrelevant", error="network fail")

    mock_llm = MagicMock()
    mock_llm.chat.side_effect = [tested_obj]
    mock_llm_cls.return_value = mock_llm
    mock_memory_log.dev_null_instance.side_effect = ["MemoryLogInstance"]

    invalid = _invalid_path(tmp_path)
    with patch("evaluations.case_builders.helper_synthetic_json.Path", return_value=invalid), \
         patch("evaluations.case_builders.helper_synthetic_json.sys.exit", side_effect=SystemExit) as mock_exit:

        with pytest.raises(SystemExit):
            HelperSyntheticJson.generate_json(
                vendor_key=VendorKey("openai", "dummy"),
                system_prompt=["system"],
                user_prompt=["user"],
                schema=schema,
            )

    #system exit invoked, so no content access but check on attributes
    assert tested_obj.has_error is True
    assert tested_obj.error == "network fail"
    assert mock_exit.mock_calls == [call(1)] 

    expected_calls = [
        call("MemoryLogInstance", "dummy", with_audit=False, temperature=1.0),
        call().set_system_prompt(["system"]),
        call().set_user_prompt(["user"]),
        call().chat(schemas=[schema]),
    ]
    assert mock_llm_cls.mock_calls == expected_calls
    assert mock_llm.chat.call_count == 1
    calls = [call.dev_null_instance()]
    assert mock_memory_log.mock_calls == calls    
