import json, pytest, hashlib
from argparse import Namespace
from unittest.mock import patch, call, ANY, MagicMock
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
    assert kwargs['schema'] == tested.schema_rubric()

    expected_system_prompt: list[str] = [
            "You are a clinical informatics expert working with a senior physician "
            "to design case-specific rubrics that assess how faithfully a medical "
            "scribe note reflects the transcript and chart.",
            "Return your answer as JSON inside a fenced ```json ... ``` block."]

    expected_user_prompt: list[str] = [
            "Task: design a grading rubric for *documentation fidelity*.",
            "Definition of fidelity: how accurately the note captures what was said "
            "or implied in the transcript, using relevant context from the chart. "
            "Do not judge clinical decisions—only documentation fidelity.",
            "Follow three steps internally, but output **only** the final rubric:",
            " 1. Identify key events/statements in transcript & chart.",
            " 2. Decide what an ideal scribe must capture.",
            " 3. Produce the rubric as a JSON array of objects.",
            "Each object keys:",
            " - criterion (string) — must start with with \"Reward for\" or \"Penalize for\"",
            " - weight    (int 0-100)",
            " - sense     (\"positive\" | \"negative\")",
            "Include at least one criterion on overall completeness and one on chart-copy fidelity.",
            "Your JSON **must** conform to the following JSON Schema:",
            "```json",
            json.dumps(tested.schema_rubric(), indent=2),
            "```",
            "Wrap the JSON array in a fenced ```json block and output nothing else.",
            "--- BEGIN TRANSCRIPT JSON ---",
            transcript.read_text(),
            "--- END TRANSCRIPT JSON ---",
            "--- BEGIN CHART JSON ---",
            chart.read_text(),
            "--- END CHART JSON ---",
            "--- BEGIN CANVAS CONTEXT JSON ---",
           context.read_text(),
            "--- END CANVAS CONTEXT JSON ---",]
    
    expected_system_prompt_md5 = hashlib.md5("\n".join(expected_system_prompt).encode()).hexdigest()
    expected_user_prompt_md5 = hashlib.md5("\n".join(expected_user_prompt).encode()).hexdigest()
    tested_system_prompt_md5 = hashlib.md5("\n".join(kwargs['system_prompt']).encode()).hexdigest()
    tested_user_prompt_md5 = hashlib.md5("\n".join(kwargs['user_prompt']).encode()).hexdigest()

    assert kwargs["system_prompt"] == expected_system_prompt
    assert kwargs["user_prompt"] == expected_user_prompt
    

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