from types import SimpleNamespace
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# module under test
from evaluations.cases.synthetic_unit_cases import rubric_generator as rg

@pytest.fixture
def stub_paths(tmp_path):
    transcript = tmp_path / "transcript.json"
    chart = tmp_path / "chart.json"
    context = tmp_path / "ctx.json"
    transcript.write_text(json.dumps([{"speaker": "Clinician", "text": "Hello, patient!"}]))
    chart.write_text(json.dumps({"currentMedications": []}))
    context.write_text(json.dumps({"note": "canvas stub"}))
    return transcript, chart, context

def _fake_response(payload):
    return SimpleNamespace(response=payload)

def test_load_json_reads_file(tmp_path):
    sample = {"foo": 1}
    f = tmp_path / "sample.json"
    f.write_text(json.dumps(sample))

    # exercise the real helper
    assert rg.RubricGenerator.load_json(f) == sample


def test_create_llm_uses_key():
    gen = rg.RubricGenerator("MY_KEY")
    assert gen.llm.api_key == "MY_KEY"
    assert gen.llm.model == rg.Constants.OPENAI_CHAT_TEXT #checks that o3 is used as default. 

def test_build_prompt_adds_two_turns():
    g = rg.RubricGenerator("KEY")
    g.build_prompt(transcript=[{"x": 1}],
                   chart={"y": 2},
                   canvas_context={"z": 3})

    prompts = g.llm.prompts
    # exactly system + user
    assert len(prompts) == 2
    assert prompts[0].role == rg.LlmTurn(role="system", text=[]).role
    assert prompts[1].role == rg.LlmTurn(role="user", text=[]).role
    
    #just check the prompt includes one of the lines.
    joined = "\n".join(prompts[1].text)
    assert "--- BEGIN TRANSCRIPT JSON ---" in joined


@patch.object(rg.RubricGenerator, "load_json")
def test_generate_success(load_json_mock, monkeypatch, stub_paths, tmp_path):
    load_json_mock.side_effect = lambda p: json.loads(Path(p).read_text())
    rubric_json = [
        {"criterion": "Reward for capturing greeting",
         "weight": 10, "sense": "positive"}
    ]
    gen = rg.RubricGenerator("KEY")
    monkeypatch.setattr(gen.llm, "request", lambda: _fake_response(json.dumps(rubric_json)))

    out = tmp_path / "rubric.json"
    gen.generate(*stub_paths, output_path=out)

    saved = json.loads(out.read_text())
    assert saved == rubric_json


@patch.object(rg.RubricGenerator, "load_json")
def test_generate_fallback_raw(load_json_mock, monkeypatch, stub_paths, tmp_path):
    load_json_mock.side_effect = lambda p: json.loads(Path(p).read_text())
    gen = rg.RubricGenerator("KEY")
    monkeypatch.setattr(
        gen.llm, "request", lambda: _fake_response("NOT-JSON")
    )

    out = tmp_path / "rubric_raw.txt"
    gen.generate(*stub_paths, output_path=out)

    assert out.read_text() == "NOT-JSON"
