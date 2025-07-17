import json, pytest
from pathlib import Path
from argparse import Namespace
from unittest.mock import patch, call, ANY, MagicMock
from evaluations.case_builders.rubric_generator import RubricGenerator, HelperEvaluation
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings import Settings
from evaluations.case_builders.helper_synthetic_json import HelperSyntheticJson

@pytest.fixture
def tmp_paths(tmp_path):
    transcript_path = tmp_path / "transcript.json"
    chart_path = tmp_path / "chart.json"
    canvas_context_path = tmp_path / "canvas_context.json"
    output_path = tmp_path / "rubric_out.json"

    transcript_path.write_text(json.dumps([{"speaker": "Clinician", "text": "Hi"}]))
    chart_path.write_text(json.dumps({"meds": []}))
    canvas_context_path.write_text(json.dumps({"foo": "bar"}))

    return transcript_path, chart_path, canvas_context_path, output_path

def test_load_json(tmp_path):
    expected = {"hello": "world"}
    path = tmp_path / "sample.json"
    path.write_text(json.dumps(expected))

    result = RubricGenerator.load_json(path)
    assert result == expected

def test_schema_rubric():
    tested = RubricGenerator(VendorKey("openai", "KEY"))
    schema = tested.schema_rubric()

    assert schema["type"] == "array"
    assert schema["minItems"] == 1
    props = set(schema["items"]["properties"])
    required = set(schema["items"]["required"])
    assert props == {"criterion", "weight", "sense"}
    assert required == props

@patch("evaluations.case_builders.rubric_generator.HelperSyntheticJson.generate_json")
def test_generate__success(mock_generate_json, tmp_paths):
    transcript, chart, context, output_path = tmp_paths
    expected = [{"criterion": "Reward X", "weight": 10, "sense": "positive"}]
    mock_generate_json.return_value = expected

    tested = RubricGenerator(VendorKey("openai", "KEY"))
    tested.generate(transcript, chart, context, output_path=output_path)

    result = json.loads(output_path.read_text())
    assert result == expected

    calls = mock_generate_json.mock_calls
    assert calls == [
        call(
            vendor_key=tested.vendor_key,
            system_prompt=ANY,
            user_prompt=ANY,
            schema=tested.schema_rubric()
        )
    ]
    #check for keyword arguments.
    _, kwargs = mock_generate_json.call_args
    assert kwargs['vendor_key'] == tested.vendor_key
    assert 'system_prompt' in kwargs
    assert 'user_prompt' in kwargs
    assert kwargs['schema'] == tested.schema_rubric()

@patch("evaluations.case_builders.rubric_generator.HelperSyntheticJson.generate_json", side_effect=SystemExit(1))
def test_generate__fallback(mock_generate_json, tmp_paths):
    transcript, chart, context, output_path = tmp_paths
    tested = RubricGenerator(VendorKey("openai", "KEY"))

    with pytest.raises(SystemExit) as exc:
        tested.generate(transcript, chart, context, output_path=output_path)
    assert exc.value.code == 1
    mock_generate_json.assert_called_once()

def test_main(tmp_paths):
    transcript_path, chart_path, context_path, output_path = tmp_paths
    fake_args = Namespace(
        transcript_path=transcript_path,
        chart_path=chart_path,
        canvas_context_path=context_path,
        output_path=output_path,
    )

    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey("openai", "MYKEY")
    call_info = {}

    def fake_generate(self, *, transcript_path, chart_path, canvas_context_path, output_path):
        call_info["self"]                = self
        call_info["transcript_path"]     = transcript_path
        call_info["chart_path"]          = chart_path
        call_info["canvas_context_path"] = canvas_context_path
        call_info["output_path"]         = output_path
        call_info["called"]              = True

    with patch("evaluations.case_builders.rubric_generator.argparse.ArgumentParser.parse_args",
               return_value=fake_args), \
         patch.object(HelperEvaluation, "settings", classmethod(lambda cls: dummy_settings)), \
         patch.object(RubricGenerator, "generate", fake_generate):
         RubricGenerator.main()

    assert call_info.get("called") is True
    assert isinstance(call_info["self"], RubricGenerator)
    assert call_info["transcript_path"] == transcript_path
    assert call_info["chart_path"] == chart_path
    assert call_info["canvas_context_path"] == context_path
    assert call_info["output_path"] == output_path