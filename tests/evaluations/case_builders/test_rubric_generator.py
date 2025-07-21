import json, pytest, hashlib
from argparse import Namespace
from unittest.mock import patch, MagicMock
from evaluations.case_builders.rubric_generator import RubricGenerator, HelperEvaluation
from evaluations.constants import Constants
from hyperscribe.structures.vendor_key import VendorKey

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
    result = tested.schema_rubric()
    expected = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 1,
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string",
                                  "description": "dimension of note being evaluated"},
                    "weight":    {"type": "integer", 
                                  "description": "how much criterion is worth", 
                                  "minimum": 0, "maximum": 100},
                    "sense":     {"type": "string", 
                                  "description": "positive or negative direction",
                                  "enum": [Constants.POSITIVE_VALUE, Constants.NEGATIVE_VALUE]}
                },
                "required": ["criterion", "weight", "sense"],
                "additionalProperties": False
            }
        }
    
    assert result == expected


@patch.object(RubricGenerator, "schema_rubric")
@patch("evaluations.case_builders.rubric_generator.HelperSyntheticJson.generate_json")
def test_generate__success(mock_generate_json, mock_schema_rubric, tmp_paths):
    transcript, chart, context, output_path = tmp_paths
    expected = [{"criterion": "Reward X", "weight": 10, "sense": "positive"}]
    mock_generate_json.return_value = expected
    expected_schema = {"expected": "schema"}
    mock_schema_rubric.side_effect = lambda: expected_schema

    tested = RubricGenerator(VendorKey("openai", "KEY"))
    tested.generate(transcript, chart, context, output_path=output_path)

    result = json.loads(output_path.read_text())
    assert result == expected

    _, kwargs = mock_generate_json.call_args
    expected_system_md5 = "a32a64e63443ef0f076080b5be3873d9"
    expected_user_md5 = "aa9784cf40795731b20103b58a884fc7"
    result_system_md5 = hashlib.md5("\n".join(kwargs["system_prompt"]).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(kwargs["user_prompt"]).encode()).hexdigest()

    assert kwargs["vendor_key"] == tested.vendor_key
    assert kwargs["schema"] == expected_schema
    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5
    

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