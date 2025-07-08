import json, pytest
from pathlib import Path
from unittest.mock import patch
from evaluations.cases.synthetic_unit_cases import profile_generator as pg
from hyperscribe.libraries.constants import Constants
from hyperscribe.structures.vendor_key import VendorKey

@pytest.fixture
def dummy_profiles():
    return {
        "Patient 1": "Alice takes lisinopril. Simple renewal.",
        "Patient 2": "Bob switched from metformin to insulin. Complex."
    }

def fake_llm_response(n_pairs):
    """Return raw LLM json string for count=n_pairs."""
    data = {f"Patient {i+1}": f"Mock narrative {i+1}." for i in range(n_pairs)}
    return json.dumps(data)

def test_patient_profile_summarize():
    txt = "First sentence. Second sentence."
    p = pg.PatientProfile("x", txt)
    assert p.summarize_scenario() == "First sentence"


def test_create_llm_uses_key():
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    generator = pg.PatientProfileGenerator(vendor_key)
    llm = generator._create_llm()
    assert llm.model == Constants.OPENAI_CHAT_TEXT_O3
    assert llm.api_key == "MY_KEY"
    

@patch.object(pg.PatientProfileGenerator, "_create_llm")
def test_generate_batch_parses_llm_json(mock_llm_cls):
    #uses .request() to return the fake string
    instance = mock_llm_cls.return_value
    instance.request.return_value.response = fake_llm_response(3)
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    g = pg.PatientProfileGenerator(vendor_key)
    batch = g.generate_batch(batch_num=1, count=3)

    # expectations–three sentences in seen_scenarios 
    assert len(batch) == 3
    assert [p.name for p in batch] == ["Patient 1", "Patient 2", "Patient 3"]
    assert len(g.seen_scenarios) == 3
    assert all(s.startswith("Mock narrative") for s in g.seen_scenarios)

def test_pipeline_saves_files(tmp_path, dummy_profiles):
    out_json = tmp_path / "combined.json"
    json_strings = pg.PatientProfilePipeline("KEY", str(out_json))
    json_strings.all_profiles = dummy_profiles

    #test whether dummy profiles are accurately saved + combined.
    json_strings._save_combined()
    json_strings._save_individuals()
    saved = json.loads(out_json.read_text())
    assert saved == dummy_profiles

    # each individual dir contains profile.json with correct payload
    for name, narrative in dummy_profiles.items():
        dir_name = name.replace(" ", "_")
        pfile = tmp_path / dir_name / "profile.json"
        assert pfile.exists()
        assert json.loads(pfile.read_text()) == {name: narrative}

@patch.object(pg.PatientProfileGenerator, "generate_batch")
def test_pipeline_run_end_to_end(mock_gen_batch, tmp_path):
    # fabricate two batches x 2 profiles each
    mock_gen_batch.side_effect = [
        [pg.PatientProfile("Patient 1", "n1"), pg.PatientProfile("Patient 2", "n2")],
        [pg.PatientProfile("Patient 3", "n3"), pg.PatientProfile("Patient 4", "n4")],
    ]

    out_json = tmp_path / "profiles.json"
    json_profiles = pg.PatientProfilePipeline("KEY", str(out_json))
    json_profiles.run(batches=2, batch_size=2)

    combined = json.loads(out_json.read_text())
    assert len(combined) == 4
    assert set(combined) == {"Patient 1", "Patient 2", "Patient 3", "Patient 4"}
    assert mock_gen_batch.call_count == 2
