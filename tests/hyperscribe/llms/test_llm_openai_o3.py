import json
from unittest.mock import MagicMock
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.libraries.memory_log import MemoryLog

def test_to_dict_removes_modalities():
    mock_log = MagicMock(spec=MemoryLog)
    llm = LlmOpenaiO3(memory_log=mock_log, api_key="sk-test", with_audit=True, temperature=0.5)

    #patching to_dict with a fake dict to test
    parent_dict = {"modalities": "text", "other": "value"}
    llm.__class__.__bases__[0].to_dict = lambda self, for_log: parent_dict.copy()

    result = llm.to_dict(for_log=True)

    assert "modalities" not in result
    assert result == {"other": "value"}