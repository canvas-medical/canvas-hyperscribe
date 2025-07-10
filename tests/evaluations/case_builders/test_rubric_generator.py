import json
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from evaluations.case_builders.rubric_generator import main, RubricGenerator
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings    import Settings
from evaluations.case_builders.synthetic_json_helper import generate_json

@pytest.fixture
def tmp_paths(tmp_path):
    transcript = tmp_path / "transcript.json"
    chart      = tmp_path / "chart.json"
    context    = tmp_path / "ctx.json"
    transcript.write_text(json.dumps([{"speaker": "Clinician", "text": "Hi"}]))
    chart.write_text(json.dumps({"meds": []}))
    context.write_text(json.dumps({"foo": "bar"}))
    return transcript, chart, context, tmp_path / "rubric_out.json"

def test_load_json_reads_file(tmp_path):
    tested = RubricGenerator
    expected = {"hello": "world"}
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(expected))

    result = tested.load_json(path)
    assert result == expected

def test_schema_rubric_structure():
    tested = RubricGenerator(VendorKey("openai", "KEY"))
    result = tested.schema_rubric()

    assert result["type"] == "array"
    assert result["minItems"] == 1
    expected_props = {"criterion", "weight", "sense"}
    assert set(result["items"]["properties"]) == expected_props
    assert set(result["items"]["required"]) == expected_props

@patch("evaluations.case_builders.rubric_generator.generate_json")
def test_generate_success_writes_output(mock_generate_json, tmp_paths):
    transcript, chart, context, output_path = tmp_paths
    expected = [{"criterion": "Reward X", "weight": 10, "sense": "positive"}]
    mock_generate_json.return_value = expected

    tested = RubricGenerator(VendorKey("openai", "KEY"))
    tested.generate(transcript, chart, context, output_path=output_path)

    result = json.loads(output_path.read_text())
    assert result == expected

    mock_generate_json.assert_called_once()
    _, kwargs = mock_generate_json.call_args
    assert kwargs["vendor_key"].api_key == "KEY"
    assert isinstance(kwargs["system_prompt"], list)
    assert isinstance(kwargs["user_prompt"], list)
    assert kwargs["schema"] == tested.schema_rubric()
    assert kwargs["retries"] == 3

@patch("evaluations.case_builders.rubric_generator.generate_json", side_effect=SystemExit(1))
def test_generate_fallback_propagates_exit(mock_generate_json, tmp_paths):
    transcript, chart, context, output_path = tmp_paths
    tested = RubricGenerator(VendorKey("openai", "KEY"))

    with pytest.raises(SystemExit) as exc:
        tested.generate(transcript, chart, context, output_path=output_path)
    assert exc.value.code == 1
    mock_generate_json.assert_called_once()

def test_main_parses_args_and_invokes_generate(tmp_path, monkeypatch):
    tested = main

    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey("openai", "MYKEY")
    monkeypatch.setattr(Settings, "from_dictionary", classmethod(lambda cls, env: dummy_settings))

    transcript = tmp_path / "transcript.json"; transcript.write_text(json.dumps([]))
    chart = tmp_path / "chart.json"; chart.write_text(json.dumps({}))
    context = tmp_path / "ctx.json"; context.write_text(json.dumps({}))
    out = tmp_path / "out.json"

    call_args = {}
    def fake_generate(self, transcript_path, chart_path, canvas_context_path, output_path):
        call_args["self"] = self
        call_args["transcript_path"] = transcript_path
        call_args["chart_path"] = chart_path
        call_args["canvas_context_path"] = canvas_context_path
        call_args["output_path"] = output_path
        call_args["called"] = True

    monkeypatch.setattr(RubricGenerator, "generate", fake_generate)
    monkeypatch.setattr(sys, "argv", [
        "prog",
        str(transcript),
        str(chart),
        str(context),
        str(out),
    ])

    tested()

    assert call_args["called"] is True
    assert isinstance(call_args["self"], RubricGenerator)
    assert call_args["transcript_path"] == transcript
    assert call_args["chart_path"] == chart
    assert call_args["canvas_context_path"] == context
    assert call_args["output_path"] == out