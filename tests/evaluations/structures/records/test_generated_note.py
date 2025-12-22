from evaluations.structures.records.generated_note import GeneratedNote
from canvas_sdk.clients.llms import LlmTokens
from tests.helper import is_namedtuple


def test_class():
    tested = GeneratedNote
    fields = {
        "case_id": int,
        "cycle_duration": int,
        "cycle_count": int,
        "cycle_transcript_overlap": int,
        "text_llm_vendor": str,
        "text_llm_name": str,
        "note_json": list,
        "hyperscribe_version": str,
        "staged_questionnaires": dict,
        "transcript2instructions": dict,
        "instruction2parameters": dict,
        "parameters2command": dict,
        "failed": bool,
        "errors": dict,
        "experiment": bool,
        "token_counts": LlmTokens,
        "id": int,
    }
    assert is_namedtuple(tested, fields)


def test_default():
    result = GeneratedNote(case_id=7)
    assert result.case_id == 7
    assert result.cycle_duration == 0
    assert result.cycle_count == 0
    assert result.cycle_transcript_overlap == 0
    assert result.text_llm_vendor == ""
    assert result.text_llm_name == ""
    assert result.note_json == []
    assert result.hyperscribe_version == ""
    assert result.staged_questionnaires == {}
    assert result.transcript2instructions == {}
    assert result.instruction2parameters == {}
    assert result.parameters2command == {}
    assert result.failed is False
    assert result.errors == {}
    assert result.token_counts == LlmTokens(prompt=0, generated=0)
    assert result.id == 0
