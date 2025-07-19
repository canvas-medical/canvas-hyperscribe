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
    SyntheticProfileGenerator.output_path = output_path
    SyntheticProfileGenerator.all_profiles = dummy_profiles
    SyntheticProfileGenerator._save_combined()

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


@patch("evaluations.case_builders.synthetic_profile_generator.HelperSyntheticJson.generate_json")
def test_generate_batch(mock_generate_json, fake_llm_response, vendor_key: VendorKey):
    n = 3
    expected = fake_llm_response(n)
    mock_generate_json.return_value = expected

    tested = SyntheticProfileGenerator(vendor_key, "out.json")
    batch_num = 2
    count = 3

    result = tested.generate_batch(batch_num, count)
    schema = tested.schema_batch(count)

    expected_system_prompt = [
        "You are a clinical‑informatics expert generating synthetic patient profiles for testing medication‑management AI systems.",
        "Return your answer as JSON inside a fenced ```json ... ``` block.",
        "The response **must** conform to the following JSON Schema:",
        "```json",
        json.dumps(schema, indent=2),
        "```",
    ]

    expected_user_prompt = [
        f"Create a JSON object with {count} key-value pairs labeled "
        f"\"Patient {1 + (batch_num-1)*count}\" through \"Patient {batch_num*count}\". "
        "Each value must be a 3-to-5-sentence medication-history narrative "
        "written for a broad audience (≈ 40-60 plain-English words).",
        "",
        "Include **at least two** LOW-complexity patients "
        "(single renewal, first-time Rx, or simple dose tweak). Other patients may be moderate "
        "or high complexity, guided by the diversity checklist below:",
        "- Age bands: <18, 18-30, 30-50, 50-70, >70.",
        "- Social context: homelessness, language barrier, uninsured, rural isolation, etc.",
        "- Novel drug classes: GLP-1 agonists, oral TKIs, depot antipsychotics, inhaled steroids, biologics, antivirals, contraception, chemo, herbals.",
        "- Edge-case themes: pregnancy, QT risk, REMS, dialysis, polypharmacy/deprescribing, travel medicine, etc.",
        "",
        "Already-seen motifs → None yet. **Avoid** re-using templates like ACE-inhibitor-to-ARB cough, long-term warfarin INR drift, or COPD tiotropium boilerplate.",
        "",
        "Write in clear prose with minimal jargon. If a medical abbreviation is unavoidable, "
        "spell it out the first time (e.g., “twice-daily (BID)”). Prefer full words: “by mouth” "
        "over “PO”, “under the skin” over “SC”. Vary openings: lead with social detail, "
        "medication list, or family history.",
        "",
        "Each narrative MUST include:",
        "• Current medicines in plain words, with some cases not having complete details.",
        "• A scenario involving medication management—straightforward new prescriptions, simple dose adjustments, or complex edge cases involving risky medications, polypharmacy, or social barriers.",
        "• Any key allergy, condition, or social barrier.",
        "",
        "Do NOT write SOAP notes, vital signs, or assessments.",
        "",
        "Wrap the JSON in a fenced ```json block and output nothing else.",
    ]

    expected_call = call(
        vendor_key=vendor_key,
        system_prompt=expected_system_prompt,
        user_prompt=expected_user_prompt,
        schema=schema)
    assert mock_generate_json.mock_calls == [expected_call]
    
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

    with patch.object(HelperEvaluation, "settings", new=classmethod(lambda cls: dummy_settings)), \
         patch.object(ArgumentParser, "parse_args", new=lambda self: args), \
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