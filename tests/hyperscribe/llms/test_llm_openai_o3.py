from unittest.mock import MagicMock
from hyperscribe.llms.llm_openai_o3 import LlmOpenaiO3
from hyperscribe.libraries.memory_log import MemoryLog


def test_to_dict_removes_modalities():
    mock_log = MagicMock(spec=MemoryLog)
    llm = LlmOpenaiO3(memory_log=mock_log, api_key="sk-test", with_audit=True, temperature=0.5)
    parent_cls = llm.__class__.__bases__[0]

    # modalities are present.
    parent_cls.to_dict = lambda self, for_log: {"modalities": "text", "other": "value"}
    result = llm.to_dict(for_log=True)
    assert result == {"other": "value"}
    assert "modalities" not in result

    # modalities not present.
    parent_cls.to_dict = lambda self, for_log: {"other": "value"}
    result_no_modalities = llm.to_dict(for_log=True)
    assert result_no_modalities == {"other": "value"}
    assert "modalities" not in result_no_modalities
