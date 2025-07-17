import json, sys, re, pytest
from pathlib import Path
from unittest.mock import patch, call, MagicMock, ANY
from argparse import ArgumentParser, Namespace
from evaluations.case_builders.synthetic_profile_generator import SyntheticProfileGenerator, HelperEvaluation
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


def test_init_initializes_generator(tmp_path, vendor_key: VendorKey):
    output_path = tmp_path / "combined.json"
    tested = SyntheticProfileGenerator(vendor_key, output_path)
    expected_path = (tmp_path / "combined.json")
    assert tested.vendor_key == vendor_key
    assert tested.output_path == expected_path
    assert tested.seen_scenarios == []
    assert tested.all_profiles == {}

def test_extract_initial_fragment(vendor_key: VendorKey):
    tested = SyntheticProfileGenerator(vendor_key, "out.json")
    narrative = "First sentence. Second sentence."
    expected = "First sentence"
    result = tested._extract_initial_fragment(narrative)
    assert result == expected


def test__save_combined(tmp_path, dummy_profiles: dict, vendor_key: VendorKey):
    out_file = tmp_path / "combined.json"
    tested = SyntheticProfileGenerator(vendor_key, out_file)
    tested.all_profiles = dummy_profiles
    tested._save_combined()
    result = json.loads(out_file.read_text())
    expected = dummy_profiles
    assert result == expected


def test__save_individuals(tmp_path, dummy_profiles: dict, vendor_key: VendorKey):
    out_file = tmp_path / "combined.json"
    tested = SyntheticProfileGenerator(vendor_key, out_file)
    tested.all_profiles = dummy_profiles
    tested._save_individuals()

    for name, narrative in dummy_profiles.items():
        dir_name = re.sub(r"\s+", "_", name.strip())
        profile_path = tmp_path / dir_name / "profile.json"
        assert profile_path.exists()
        result = json.loads(profile_path.read_text())
        expected = {name: narrative}
        assert result == expected


def test_schema_batch(vendor_key: VendorKey):
    tested = SyntheticProfileGenerator(vendor_key, "out.json")
    count = 4
    result = tested.schema_batch(count)
    expected = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "minProperties": count,
        "maxProperties": count,
        "patternProperties": {r"^Patient\s\d+$": { "type": "string" }},
        "additionalProperties": False
    }
    assert result == expected


@patch("evaluations.case_builders.synthetic_profile_generator.HelperSyntheticJson.generate_json")
def test_generate_batch(mock_generate_json, fake_llm_response, vendor_key: VendorKey):
    n = 3
    expected = fake_llm_response(n)
    mock_generate_json.return_value = expected

    tested = SyntheticProfileGenerator(vendor_key, "out.json")
    batch_num = 2
    count = 3

    result = tested.generate_batch(batch_num, count)
    expected_keys = [f"Patient {i+1}" for i in range(count)]
    assert list(result.keys()) == expected_keys
    assert result == expected
    assert len(tested.seen_scenarios) == count
    for fragment in tested.seen_scenarios:
        assert fragment.startswith("Mock narrative")

    calls = [call(vendor_key=vendor_key, system_prompt=ANY,
            user_prompt=ANY,
            schema=tested.schema_batch(count))]
    assert mock_generate_json.mock_calls == calls
    assert mock_generate_json.call_count == 1

    _, kwargs = mock_generate_json.call_args

    #kwarg validation
    assert kwargs["vendor_key"] == vendor_key
    assert kwargs["schema"] == tested.schema_batch(count)

    #system prompt validation
    system_prompt = kwargs["system_prompt"]
    assert isinstance(system_prompt, list)
    assert any("clinical‑informatics expert" in line for line in system_prompt)
    assert any("```json" in line for line in system_prompt)
    assert any("http://json-schema.org/draft-07/schema#" in line for line in system_prompt)

    #user prompt validation
    user_prompt = kwargs["user_prompt"]
    assert isinstance(user_prompt, list)
    assert any("LOW-complexity patients" in line for line in user_prompt)
    assert any("JSON object with" in line for line in user_prompt)
    assert any("Each narrative MUST include" in line for line in user_prompt)
    assert any("Do NOT write SOAP notes" in line for line in user_prompt)

@patch.object(SyntheticProfileGenerator, "_save_individuals")
@patch.object(SyntheticProfileGenerator, "_save_combined")
@patch.object(SyntheticProfileGenerator, "generate_batch")
def test_run(mock_generate_batch, mock_save_combined, mock_save_individuals, vendor_key: VendorKey):
    tested = SyntheticProfileGenerator(vendor_key, "out.json")
    batches = 2
    batch_size = 5
    tested.run(batches=batches, batch_size=batch_size)

    expected_calls = [call(i, batch_size) for i in range(1, batches + 1)]
    mock_generate_batch.assert_has_calls(expected_calls, any_order=False)
    mock_save_combined.assert_called_once()
    mock_save_individuals.assert_called_once()

def test_main(tmp_path):
    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey("openai", "MAIN_KEY")

    run_calls = []
    def fake_run(self, batches, batch_size):
        run_calls.append((self, batches, batch_size))

    #run 1 for no directory
    output_path = tmp_path / "out.json"
    args = Namespace(batches=2, batch_size=5, output=output_path)

    with patch.object(HelperEvaluation, "settings", new=classmethod(lambda cls: dummy_settings)), \
         patch.object(ArgumentParser, "parse_args", new=lambda self: args), \
         patch.object(SyntheticProfileGenerator, "run", new=fake_run), \
         patch("pathlib.Path.mkdir") as mock_mkdir_1:

        SyntheticProfileGenerator.main()
        expected_calls = [call(parents=True, exist_ok=True)]
        assert mock_mkdir_1.mock_calls == expected_calls


    assert len(run_calls) == 1
    #call 1
    instance, batches, batch_size = run_calls[0]
    assert isinstance(instance, SyntheticProfileGenerator)
    assert instance.vendor_key.api_key == "MAIN_KEY"
    assert batches == 2
    assert batch_size == 5