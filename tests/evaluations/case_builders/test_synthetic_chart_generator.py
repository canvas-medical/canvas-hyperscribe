import json, uuid, pytest, hashlib
from pathlib import Path
from argparse import Namespace, ArgumentParser
from unittest.mock import patch, MagicMock, call
from typing import Any
from evaluations.case_builders.synthetic_chart_generator import SyntheticChartGenerator, HelperEvaluation, HelperSyntheticJson
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.limited_cache import LimitedCache

def test_init():
    expected_vendor_key = VendorKey(vendor="openai", api_key="API_KEY_123")
    expected_profiles = {"Patient A": "Profile text"}
    expected_output = Path("/tmp/outdir")
    expected_example = {"foo": "bar"}

    tested = SyntheticChartGenerator(expected_vendor_key, expected_profiles, expected_output, expected_example)
    assert tested.vendor_key == expected_vendor_key
    assert tested.profiles == expected_profiles
    assert tested.output == expected_output
    assert tested.example_chart == expected_example

def test_load_json(tmp_path):
    expected = {"a": 1, "b": 2}
    data_file = tmp_path / "data.json"
    data_file.write_text(json.dumps(expected))

    result = SyntheticChartGenerator.load_json(data_file)
    assert result == expected

def test_schema_chart():
    example_chart = {"cond": [], "meds": []}
    tested = SyntheticChartGenerator(
        VendorKey("vendor", "key"), {}, Path("."), example_chart)

    result_schema = tested.schema_chart()

    assert result_schema["description"] == "example Canvas-compatible chart"
    assert result_schema["type"] == "object"
    assert result_schema["additionalProperties"] is False

    #properties assertion (including description)
    properties = result_schema["properties"]
    assert set(properties.keys()) == {"cond", "meds", "description"}
    assert properties["cond"] == {"type": "array"}
    assert properties["meds"] == {"type": "array"}
    assert properties["description"] == {"type": "string"}
    assert set(result_schema["required"]) == {"cond", "meds"}
    assert "description" not in result_schema["required"]


@patch("evaluations.case_builders.synthetic_chart_generator.HelperSyntheticJson.generate_json")
def test_generate_chart_for_profile(mock_generate_json, tmp_path):
    tested_key = VendorKey(vendor="openai", api_key="LLMKEY")
    dummy_chart = {"example": "chart"}
    dummy_profiles =  profiles = {"P1*": "text1", "P2!": "text2"}
    tested = SyntheticChartGenerator(tested_key, dummy_profiles, tmp_path, dummy_chart)

    profile_text = "irrelevant profile"
    expected_chart = {"cond": ["X"], "meds": []}
    mock_generate_json.side_effect = [expected_chart]

    result = tested.generate_chart_for_profile(profile_text)
    assert result == expected_chart

    kwargs = mock_generate_json.call_args.kwargs
    expected_schema = tested.schema_chart()
    assert kwargs["vendor_key"] == tested_key
    assert kwargs["schema"] == expected_schema

    expected_system_prompt = [
        "You are generating a Canvas‑compatible `limited_chart.json` for a synthetic patient.",
        "Return your answer as JSON inside a fenced ```json ... ``` block.",
        "Only include fields shown in the example structure; leave irrelevant categories as empty arrays.",
    ]
    assert kwargs["system_prompt"] == expected_system_prompt
        
    expected_user_prompt = [
        f"Patient profile: {profile_text}",
        "",
        "Here is the required JSON structure:",
        "```json",
        json.dumps(dummy_chart, indent=2),
        "```",
        "",
        "Your JSON **must** conform to the following JSON Schema:",
        "```json",
        json.dumps(expected_schema, indent=2),
        "```",
        "",
        "Be strict:",
        "• Include only conditions the patient *has or was diagnosed with*.",
        "• Include only medications the patient *is actually taking*.",
        "• Do not fabricate information beyond the profile.",
    ]
    assert kwargs["user_prompt"] == expected_user_prompt

    expected_call = call(
        vendor_key=tested_key,
        system_prompt=expected_system_prompt,
        user_prompt=expected_user_prompt,
        schema=expected_schema
    )
    assert mock_generate_json.mock_calls == [expected_call]

@patch("evaluations.case_builders.synthetic_chart_generator.LimitedCache.load_from_json")
def test_validate_chart__success(mock_load):
    tested_chart = {"foo": "bar"}
    tested = SyntheticChartGenerator(VendorKey("v", "k"), {}, Path("."), {})
    
    tested.validate_chart(tested_chart)
    
    assert mock_load.mock_calls == [call(tested_chart)]

@patch("evaluations.case_builders.synthetic_chart_generator.LimitedCache.load_from_json", side_effect=Exception("boom"))
def test_validate_chart__invalid_structure(mock_load):
    tested_chart = {"bad": True}
    tested = SyntheticChartGenerator(VendorKey("v", "k"), {}, Path("."), {})

    with pytest.raises(ValueError) as exc_info:
        tested.validate_chart(tested_chart)

    assert "Invalid limited_chart.json structure: boom" in str(exc_info.value)
    assert mock_load.mock_calls == [call(tested_chart)]

def test_assign_valid_uuids():
    tested = SyntheticChartGenerator(VendorKey("v", "k"), {}, Path("/"), {})
    input_chart = { "uuid": "old", "nested": [{"uuid": "old2"}, {"not_uuid": 123}]}
    result = tested.assign_valid_uuids(input_chart)

    assert result["uuid"] != "old"
    uuid.UUID(result["uuid"])
    nested_uuid = result["nested"][0]["uuid"]
    assert nested_uuid != "old2"
    uuid.UUID(nested_uuid)
    assert result["nested"][1]["not_uuid"] == 123


@patch.object(SyntheticChartGenerator, "generate_chart_for_profile", side_effect=[{"some": "data1"}, {"some": "data2"}])
@patch.object(SyntheticChartGenerator, "validate_chart")
@patch.object(SyntheticChartGenerator, "assign_valid_uuids", side_effect=lambda chart: {"assigned": chart["some"]})
def test_run_range(mock_assign, mock_validate, mock_generate, tmp_path, capsys):
    profiles = {"P1*": "text1", "P2!": "text2"}
    output_dir = tmp_path / "out"
    tested = SyntheticChartGenerator(VendorKey("v", "k"), profiles, output_dir, {})

    tested.run_range(1, 2)

    assert mock_generate.call_count == 2
    assert mock_validate.call_count == 2
    assert mock_assign.call_count == 2

    #verifying calls for generate_chart_for_profile, validate, and assign.
    expected_generate_calls = [call("text1"), call("text2")]
    assert mock_generate.mock_calls == expected_generate_calls

    expected_validate_calls = [call({"some": "data1"}), call({"some": "data2"})]
    assert mock_validate.mock_calls == expected_validate_calls

    expected_assign_calls = [call({"some": "data1"}), call({"some": "data2"})]
    assert mock_assign.mock_calls == expected_assign_calls

    for raw_name, expected_value in zip(profiles, ["data1", "data2"]):
        safe_name = "".join(c if c.isalnum() else "_" for c in raw_name)
        chart_file = output_dir / safe_name / "limited_chart.json"
        assert json.loads(chart_file.read_text()) == {"assigned": expected_value}

    output = capsys.readouterr().out
    assert "Generating limited_chart.json for P1*" in output
    assert "Saved limited_chart.json to" in output

def test_main(tmp_path):
    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey(vendor="test", api_key="MY_API_KEY")

    profiles_file = tmp_path / "profiles.json"
    example_file = tmp_path / "example.json"
    out_dir = tmp_path / "out"
    profiles_file.write_text(json.dumps({"Alice": "profile"}))
    example_file.write_text(json.dumps({"foo": "bar"}))

    load_calls: list[Path] = []
    def fake_load_json(cls, path: Path):
        load_calls.append(path)
        return json.loads(path.read_text())

    run_calls: dict[str, Any] = {}
    def fake_run_range(self, start: int, limit: int):
        run_calls["instance"] = self
        run_calls["start"] = start
        run_calls["limit"] = limit

    with patch.object(HelperEvaluation, "settings", classmethod(lambda cls: dummy_settings)), \
        patch.object(SyntheticChartGenerator, "load_json", classmethod(fake_load_json)), \
        patch.object(SyntheticChartGenerator, "run_range", fake_run_range), \
        patch.object(ArgumentParser, "parse_args", lambda self: Namespace(
            input=profiles_file,
            example=example_file,
            output=out_dir,
            start=1,
            limit=3)):
        SyntheticChartGenerator.main()

    assert load_calls == [profiles_file, example_file]
    instance = run_calls["instance"]
    assert isinstance(instance, SyntheticChartGenerator)
    assert instance.vendor_key.api_key == "MY_API_KEY"
    assert run_calls["start"] == 1
    assert run_calls["limit"] == 3