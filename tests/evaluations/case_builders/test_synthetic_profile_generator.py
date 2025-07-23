import json, re, pytest, hashlib
from unittest.mock import patch, call, MagicMock
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


def test___init__(tmp_path, vendor_key: VendorKey):
    output_path = tmp_path / "combined.json"
    tested = SyntheticProfileGenerator(vendor_key, output_path)
    expected_path = (tmp_path / "combined.json")
    assert tested.vendor_key == vendor_key
    assert tested.output_path == expected_path
    assert tested.seen_scenarios == []
    assert tested.all_profiles == {}

def test__extract_initial_fragment(tmp_path, vendor_key: VendorKey):
    output_path = tmp_path / "out.json"
    tested = SyntheticProfileGenerator(vendor_key, output_path)
    narrative = "First sentence. Second sentence."
    expected = "First sentence"
    result = tested._extract_initial_fragment(narrative)
    assert result == expected


def test__save_combined(tmp_path, dummy_profiles: dict, vendor_key: VendorKey):
    output_path = tmp_path / "combined.json"
    tested = SyntheticProfileGenerator(vendor_key, output_path)
    tested.output_path = output_path
    tested.all_profiles = dummy_profiles
    tested._save_combined()

    result = json.loads(output_path.read_text())
    assert result == dummy_profiles


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


def test_schema_batch(tmp_path, vendor_key: VendorKey):
    output_path = tmp_path / "out.json"
    tested = SyntheticProfileGenerator(vendor_key,output_path)
    count_patients = 4
    result = tested.schema_batch(count_patients)
    expected = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "object",
            "minProperties": count_patients,
            "maxProperties": count_patients,
            "patternProperties": {
                r"^Patient\s\d+$": { "type": "string",
                                    "description": "patient profile"}
            },
            "additionalProperties": False
        }
    assert result == expected

@patch.object(SyntheticProfileGenerator, "schema_batch")
@patch("evaluations.case_builders.synthetic_profile_generator.HelperSyntheticJson.generate_json")
def test_generate_batch(mock_generate_json, mock_schema_batch, fake_llm_response, vendor_key: VendorKey):
    n = 3
    expected = fake_llm_response(n)
    mock_generate_json.return_value = expected

    tested = SyntheticProfileGenerator(vendor_key, "out.json")
    batch_num = 2
    count = 3
    expected_schema = {"expected": "schema"}
    mock_schema_batch.side_effect = lambda count: expected_schema

    result = tested.generate_batch(batch_num, count)
    assert len(mock_generate_json.mock_calls) == 1
    _, kwargs = mock_generate_json.call_args

    #reference hex digest with the patched schema_batch, must be re-digested if prompts change.
    expected_system_md5 = "d4d9c1999dcff7d0cff01745aa3da589"
    expected_user_md5 = "b3435eae8d1a3700c841178446de8c83"
    result_system_md5 = hashlib.md5("\n".join(kwargs["system_prompt"]).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(kwargs["user_prompt"]).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5
    assert kwargs["vendor_key"] == vendor_key
    assert kwargs["schema"] == expected_schema
    assert mock_schema_batch.mock_calls == [call(count)]
    
    expected_keys = [f"Patient {i+1}" for i in range(count)]
    assert list(result.keys()) == expected_keys
    assert result == expected
    assert len(tested.seen_scenarios) == count

@patch.object(SyntheticProfileGenerator, "_save_individuals")
@patch.object(SyntheticProfileGenerator, "_save_combined")
@patch.object(SyntheticProfileGenerator, "generate_batch")
def test_run(mock_generate_batch, mock_save_combined, mock_save_individuals, vendor_key: VendorKey):
    tested = SyntheticProfileGenerator(vendor_key, "out.json")
    batches = 2
    batch_size = 5
    tested.run(batches=batches, batch_size=batch_size)

    expected_generate_calls = [call(i, batch_size) for i in range(1, batches + 1)]
    assert mock_generate_batch.mock_calls == expected_generate_calls
    assert mock_save_combined.mock_calls   == [call()]
    assert mock_save_individuals.mock_calls == [call()]

def test_main(tmp_path):
    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey("openai", "MAIN_KEY")

    run_calls = []
    def fake_run(self, batches, batch_size):
        run_calls.append((self, batches, batch_size))

    output_path = tmp_path / "out.json"
    args = Namespace(batches=2, batch_size=5, output=output_path)

    with patch.object(HelperEvaluation, "settings", new=classmethod(lambda _: dummy_settings)), \
         patch.object(ArgumentParser, "parse_args", new=lambda _: args), \
         patch.object(SyntheticProfileGenerator, "run", new=fake_run), \
         patch("pathlib.Path.mkdir") as mock_mkdir_1:

        SyntheticProfileGenerator.main()
        expected_calls = [call(parents=True, exist_ok=True)]
        assert mock_mkdir_1.mock_calls == expected_calls


    assert len(run_calls) == 1
    instance, batches, batch_size = run_calls[0]
    assert isinstance(instance, SyntheticProfileGenerator)
    assert instance.vendor_key.api_key == "MAIN_KEY"
    assert batches == 2
    assert batch_size == 5