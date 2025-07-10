import json, sys, pytest
from pathlib import Path
from unittest.mock import patch, call, MagicMock

from evaluations.case_builders.synthetic_profile_generator import main, PatientProfileGenerator
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.structures.settings import Settings

@pytest.fixture
def dummy_profiles():
    return {
        "Patient 1": "Alice takes lisinopril. Simple renewal.",
        "Patient 2": "Bob switched from metformin to insulin. Complex."
    }

@pytest.fixture
def fake_llm_response():
    def _fake(n_pairs):
        data = {f"Patient {i+1}": f"Mock narrative {i+1}." for i in range(n_pairs)}
        return data
    return _fake

@pytest.fixture
def vendor_key():
    return VendorKey(vendor="openai", api_key="MY_KEY")

def test_init_initializes_generator(tmp_path, vendor_key):
    tested = PatientProfileGenerator(vendor_key, str(tmp_path / "combined.json"))
    assert tested.vendor_key == vendor_key
    assert tested.output_path == (tmp_path / "combined.json").expanduser()
    assert tested.seen_scenarios == []
    assert tested.all_profiles == {}

def test__summarize_scenario(vendor_key):
    tested = PatientProfileGenerator(vendor_key, "out.json")
    narrative = "First sentence. Second sentence."
    expected = "First sentence"
    result = tested._summarize_scenario(narrative)
    assert result == expected

def test__save_combined(tmp_path, dummy_profiles, vendor_key):
    out_file = tmp_path / "combined.json"
    tested = PatientProfileGenerator(vendor_key, str(out_file))
    tested.all_profiles = dummy_profiles
    tested._save_combined()
    result = json.loads(out_file.read_text())
    expected = dummy_profiles
    assert result == expected

def test__save_individuals(tmp_path, dummy_profiles, vendor_key):
    out_file = tmp_path / "combined.json"
    tested = PatientProfileGenerator(vendor_key, str(out_file))
    tested.all_profiles = dummy_profiles
    tested._save_individuals()

    for name, narrative in dummy_profiles.items():
        dir_name = name.replace(" ", "_")
        profile_path = tmp_path / dir_name / "profile.json"
        assert profile_path.exists()
        result = json.loads(profile_path.read_text())
        expected = {name: narrative}
        assert result == expected

@patch("evaluations.case_builders.synthetic_profile_generator.generate_json")
def test_generate_batch_parses_llm_json(mock_generate_json, fake_llm_response, vendor_key):
    n = 3
    expected = fake_llm_response(n)
    mock_generate_json.return_value = expected

    tested = PatientProfileGenerator(vendor_key, "out.json")
    batch_num = 2
    count = n

    result = tested.generate_batch(batch_num, count)
    expected_keys = [f"Patient {i+1}" for i in range(count)]
    assert list(result.keys()) == expected_keys
    assert len(tested.seen_scenarios) == count
    for scenario in tested.seen_scenarios:
        assert scenario.startswith("Mock narrative")

    mock_generate_json.assert_called_once()
    _, kwargs = mock_generate_json.call_args
    assert kwargs["vendor_key"] is vendor_key
    assert kwargs["retries"] == 3
    schema = kwargs["schema"]
    assert schema["minProperties"] == count
    assert schema["maxProperties"] == count

@patch.object(PatientProfileGenerator, "_save_individuals")
@patch.object(PatientProfileGenerator, "_save_combined")
@patch.object(PatientProfileGenerator, "generate_batch")
def test_run(mock_generate_batch, mock_save_combined, mock_save_individuals, vendor_key):
    tested = PatientProfileGenerator(vendor_key, "out.json")
    batches = 2
    batch_size = 5
    mock_generate_batch.return_value = {}

    tested.run(batches=batches, batch_size=batch_size)

    expected_calls = [call(batch_num, batch_size) for batch_num in range(1, batches + 1)]
    mock_generate_batch.assert_has_calls(expected_calls, any_order=False)
    mock_save_combined.assert_called_once_with()
    mock_save_individuals.assert_called_once_with()

@patch.object(PatientProfileGenerator, "run")
def test_main_parses_args_and_invokes_generator(mock_run, tmp_path, monkeypatch):
    tested = main

    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey("openai", "MAIN_KEY")

    monkeypatch.setattr(Settings, "from_dictionary", classmethod(lambda cls, env: dummy_settings))

    monkeypatch.setattr(sys, "argv", [
        "prog",
        "--batches", "2",
        "--batch-size", "5",
        "--output", str(tmp_path / "out.json")
    ])
    tested()
    mock_run.assert_called_once_with(batches=2, batch_size=5)