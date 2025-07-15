import json, uuid, sys, pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
from evaluations.case_builders.synthetic_chart_generator import SyntheticChartGenerator
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings import Settings

def test_init_assigns_attributes():
    expected_vendor_key = VendorKey(vendor="openai", api_key="API_KEY_123")
    expected_profiles = {"Patient A": "Profile text"}
    expected_output = Path("/tmp/outdir")
    expected_example = {"foo": "bar"}

    tested = SyntheticChartGenerator(expected_vendor_key, expected_profiles, expected_output, expected_example)

    assert tested.vendor_key == expected_vendor_key
    assert tested.profiles == expected_profiles
    assert tested.output == expected_output
    assert tested.example_chart == expected_example

def test_load_json_reads_json_file(tmp_path):
    tested = SyntheticChartGenerator()
    expected = {"a": 1, "b": 2}
    path = tmp_path / "data.json"
    path.write_text(json.dumps(expected))

    result = tested.load_json(path)
    assert result == expected

@patch("evaluations.case_builders.synthetic_chart_generator.generate_json", return_value={"cond": ["X"]})
def test_generate_chart_for_profile_uses_generate_json(mock_generate, tmp_path):
    tested_key = VendorKey(vendor="openai", api_key="LLMKEY")
    tested = SyntheticChartGenerator(tested_key, {}, tmp_path, {"example": "chart"})

    result = tested.generate_chart_for_profile("irrelevant profile")
    expected = {"cond": ["X"]}
    assert result == expected

    mock_generate.assert_called_once()
    _, kwargs = mock_generate.call_args
    assert kwargs["vendor_key"] is tested_key
    assert isinstance(kwargs["system_prompt"], list)
    assert isinstance(kwargs["user_prompt"], list)
    assert kwargs["retries"] == 3
    assert kwargs["schema"]["type"] == "object"

@patch("evaluations.case_builders.synthetic_chart_generator.LimitedCache.load_from_json")
def test_validate_chart_calls_limited_cache(mock_load):
    tested = SyntheticChartGenerator(VendorKey("v", "k"), {}, Path("/"), {})
    tested_chart = {"foo": "bar"}
    tested.validate_chart(tested_chart)
    mock_load.assert_called_once_with(tested_chart)

@patch("evaluations.case_builders.synthetic_chart_generator.LimitedCache.load_from_json", side_effect=Exception("boom"))
def test_validate_chart_raises_value_error_on_invalid_structure(mock_load):
    tested = SyntheticChartGenerator(VendorKey("v", "k"), {}, Path("/"), {})
    tested_chart = {"bad": True}

    with pytest.raises(ValueError) as exc:
        tested.validate_chart(tested_chart)
    assert "Invalid limited_chart.json structure: boom" in str(exc.value)
    mock_load.assert_called_once_with(tested_chart)

def test_assign_valid_uuids_replaces_uuid_keys():
    tested = SyntheticChartGenerator(VendorKey("v", "k"), {}, Path("/"), {})
    input_chart = {
        "uuid": "old",
        "nested": [{"uuid": "old2"}, {"not_uuid": 123}]
    }

    result = tested.assign_valid_uuids(input_chart)

    assert result["uuid"] != "old"
    uuid.UUID(result["uuid"])
    nested_uuid = result["nested"][0]["uuid"]
    assert nested_uuid != "old2"
    uuid.UUID(nested_uuid)
    assert result["nested"][1]["not_uuid"] == 123

@patch.object(SyntheticChartGenerator, "assign_valid_uuids")
@patch.object(SyntheticChartGenerator, "validate_chart")
@patch.object(SyntheticChartGenerator, "generate_chart_for_profile")
def test_run_range_creates_directories_and_writes_chart(
    mock_generate, mock_validate, mock_assign, tmp_path, capsys
):
    profiles = {"P1*": "text1", "P2!": "text2"}
    output = tmp_path / "out"
    tested = SyntheticChartGenerator(VendorKey("v", "k"), profiles, output, {})

    fake_chart = {"some": "data"}
    mock_generate.side_effect = [fake_chart, fake_chart]
    mock_assign.side_effect = lambda obj: {"assigned": True}

    tested.run_range(1, 2)

    assert mock_generate.call_count == 2
    assert mock_validate.call_count == 2
    assert mock_assign.call_count == 2

    for raw_name in profiles:
        safe = "".join(c if c.isalnum() else "_" for c in raw_name)
        folder = output / safe
        assert folder.exists()
        chart_file = folder / "limited_chart.json"
        assert chart_file.exists()
        result = json.loads(chart_file.read_text())
        expected = {"assigned": True}
        assert result == expected

    out = capsys.readouterr().out
    assert "Generating limited_chart.json for P1*" in out
    assert "Saved limited_chart.json to" in out

def test_main_parses_args_and_invokes_run_range(tmp_path, monkeypatch):
    tested = SyntheticChartGenerator.main()

    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey(vendor="test", api_key="MY_API_KEY")
    monkeypatch.setattr(
        Settings,
        "from_dictionary",
        classmethod(lambda cls, env: dummy_settings)
    )

    profiles_file = tmp_path / "profiles.json"
    example_file = tmp_path / "example.json"
    out_dir = tmp_path / "out"

    profiles_file.write_text(json.dumps({"Alice": "p"}))
    example_file.write_text(json.dumps({"foo": "bar"}))

    load_calls = []

    def fake_load(cls, path):
        load_calls.append(path)
        return json.loads(path.read_text())
    monkeypatch.setattr(SyntheticChartGenerator, "load_json", classmethod(fake_load))

    run_args = {}

    def fake_run_range(self, start, limit):
        run_args["self"] = self
        run_args["start"] = start
        run_args["limit"] = limit
    monkeypatch.setattr(SyntheticChartGenerator, "run_range", fake_run_range)

    monkeypatch.setattr(sys, "argv", [
        "prog",
        "--limit", "3",
        "--input", str(profiles_file),
        "--output", str(out_dir),
        "--example", str(example_file),
    ])

    tested()

    assert load_calls == [profiles_file, example_file]
    assert isinstance(run_args["self"], SyntheticChartGenerator)
    assert run_args["self"].vendor_key.api_key == "MY_API_KEY"
    assert run_args["start"] == 1
    assert run_args["limit"] == 3