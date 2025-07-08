import json
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import ANY
from unittest.mock import MagicMock, patch

import pytest
from evaluations.cases.synthetic_unit_cases import score_generator as gg
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.constants import Constants


@pytest.fixture
def tmp_files(tmp_path):
    """Create dummy rubric / note files and return their paths."""
    rubric = [
        {"criterion": "Reward for A", "weight": 20, "sense": "positive"},
        {"criterion": "Penalize for B", "weight": 30, "sense": "negative"},
    ]
    note = {"some": "note"}

    rubric_path = tmp_path / "rubric.json"
    note_path = tmp_path / "note.json"
    rubric_path.write_text(json.dumps(rubric))
    note_path.write_text(json.dumps(note))
    output = tmp_path / "out.json"
    return rubric_path, note_path, output, rubric, note

def _fake_response(text: str):
    req = SimpleNamespace(response=text)
    llm = SimpleNamespace(request=MagicMock(return_value=req))
    return llm

@patch.object(gg, "LlmOpenai")
def test_build_llm_uses_key(mock_openai, tmp_files):
    """
    _build_llm should instantiate LlmOpenai with the supplied key and
    call add_prompt twice (system + user).
    """
    rubric_path, note_path, output, *_ = tmp_files

    dummy_llm = MagicMock()
    mock_openai.return_value = dummy_llm  
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    grader = gg.NoteGrader(vendor_key, rubric_path, note_path, output)
    grader._build_llm()
    
    assert dummy_llm.add_prompt.call_count == 2


@patch.object(gg.NoteGrader, "_build_llm")
def test_run_happy_path(mock_build, tmp_files):
    rubric_path, note_path, output, rubric, _ = tmp_files
    llm_payload = [
        {"rationale": "good", "satisfaction": 80},
        {"rationale": "bad",  "satisfaction": 25},
    ]
    mock_build.return_value = _fake_response(json.dumps(llm_payload))

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    grader = gg.NoteGrader(vendor_key, rubric_path, note_path, output)
    grader.run()

    saved = json.loads(output.read_text())
    assert saved == [
        {"rationale": "good", "satisfaction": 80.0, "score": 16.0},
        {"rationale": "bad",  "satisfaction": 25.0, "score": -22.5}, #based on corresponding rationale
    ]


@patch.object(gg.NoteGrader, "_build_llm")
def test_run_raw_fallback(mock_build, tmp_files, monkeypatch):
    r_path, n_path, out_path, *_ = tmp_files
    raw_text = "NOT-JSON"
    mock_build.return_value = _fake_response(raw_text)
    monkeypatch.setattr(sys, "exit", lambda code=0: (_ for _ in ()).throw(SystemExit(code)))

    vendor_key = VendorKey(vendor="openai", api_key="KEY")
    grader = gg.NoteGrader(vendor_key, r_path, n_path, out_path)

    with pytest.raises(SystemExit) as exc:
        grader.run()
    assert exc.value.code == 1
    assert out_path.read_text() == raw_text
