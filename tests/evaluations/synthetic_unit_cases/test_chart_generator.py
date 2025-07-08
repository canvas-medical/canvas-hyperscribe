from pathlib import Path
import json, uuid, pytest
from unittest.mock import MagicMock, patch
from evaluations.cases.synthetic_unit_cases import chart_generator as cg
from hyperscribe.structures.vendor_key import VendorKey
from hyperscribe.libraries.constants import Constants

@pytest.fixture
def example_chart():
    return {
        "demographicStr": "",
        "currentConditions": [],
        "currentMedications": [],
        "currentAllergies": [],
        "conditionHistory": [],
        "currentGoals": [],
        "familyHistory": [],
        "surgeryHistory": [],
    }

@pytest.fixture
def dummy_profiles(tmp_path):
    patient_file = tmp_path / "profiles.json"
    json.dump({"Patient 1": "Alice takes lisinopril."}, patient_file.open("w"))
    return patient_file


def _fake_llm(payload: dict | str):
    llm = MagicMock()
    llm.request.return_value.response = json.dumps(payload) if isinstance(payload, dict) else payload
    return llm

def test_assign_valid_uuids_replaces_all():
    gen = cg.ChartGenerator.__new__(cg.ChartGenerator)
    sample = {"uuid": "x", "nested": [{"uuid": "y"}]}
    out = gen.assign_valid_uuids(sample)
    assert out["uuid"] != "x" and uuid.UUID(out["uuid"])
    assert uuid.UUID(out["nested"][0]["uuid"])

def test_create_llm_uses_key(example_chart, dummy_profiles, tmp_path):
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps(example_chart))
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    gen = cg.ChartGenerator(
        vendor_key,
        input_profiles_path=str(dummy_profiles),
        output_root_path=str(tmp_path),
        example_chart_path=str(ex))
    llm = gen._create_llm()
    assert llm.model == Constants.OPENAI_CHAT_TEXT_O3

@patch.object(cg.ChartGenerator, "_create_llm")
def test_generate_chart_for_profile_parses_json(mock_llm, example_chart, dummy_profiles, tmp_path):
    chart_payload = example_chart | {
        "currentConditions": [{"uuid": "0", "label": "Hypertension", "code": "I10"}]
    }
    mock_llm.return_value = _fake_llm(chart_payload)
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps(example_chart))
    gen = cg.ChartGenerator(
        llm_key="KEY",
        input_profiles_path=str(dummy_profiles),
        output_root_path=str(tmp_path),
        example_chart_path=str(tmp_path / "ex.json"),)
    out = gen.generate_chart_for_profile("profile text")
    assert out["currentConditions"][0]["label"] == "Hypertension"

@patch.object(cg.LimitedCache, "load_from_json")
def test_validate_chart_passes_to_cache(mock_cache, example_chart, dummy_profiles, tmp_path):
    (tmp_path / "ex.json").write_text(json.dumps(example_chart))
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    gen = cg.ChartGenerator(
        vendor_key,
        input_profiles_path=str(dummy_profiles),
        output_root_path=str(tmp_path),
        example_chart_path=str(tmp_path / "ex.json"),
    )
    gen.validate_chart(example_chart)
    mock_cache.assert_called_once_with(example_chart)

@patch.object(cg.ChartGenerator, "_create_llm")
@patch.object(cg.ChartGenerator, "validate_chart")
def test_run_creates_files(mock_validate, mock_llm, example_chart, tmp_path):
    profiles = tmp_path / "prof.json"
    json.dump({"Patient 1": "AAA"}, profiles.open("w"))
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps(example_chart))
    chart_payload = example_chart | {
        "currentMedications": [{"uuid": "x", "label": "Lisinopril 10 mg", "code": "C09AA03"}]
    }
    mock_llm.return_value = _fake_llm(chart_payload)
    out_root = tmp_path / "out"
    cg.ChartGenerator("KEY", str(profiles), str(out_root), str(ex)).run(limit=1)
    p1_dir = out_root / "Patient_1"
    assert p1_dir.exists()
    saved = json.loads((p1_dir / "limited_chart.json").read_text())
    mock_validate.assert_called_once()
    assert saved["currentMedications"][0]["uuid"] != "x"
    assert uuid.UUID(saved["currentMedications"][0]["uuid"])
    assert (p1_dir / "limited_chart.json").exists()

@patch.object(cg.ChartGenerator, "_create_llm")
def test_validate_chart_raises_on_bad(mock_llm, dummy_profiles, tmp_path, example_chart):
    bad_chart = {"foo": "bar"}
    mock_llm.return_value = _fake_llm(bad_chart)
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps(example_chart))
    gen = cg.ChartGenerator("KEY", str(dummy_profiles), str(tmp_path), str(ex))
    with patch.object(cg.LimitedCache, "load_from_json", side_effect=Exception("boom")):
        with pytest.raises(ValueError):
            gen.validate_chart(bad_chart)

@patch.object(cg.ChartGenerator, "_create_llm")
@patch.object(cg.ChartGenerator, "validate_chart")
def test_run_sanitises_directory(mock_validate, mock_llm, example_chart, tmp_path):
    profiles = tmp_path / "prof.json"
    json.dump({"Patient 1*": "AAA"}, profiles.open("w"))
    ex = tmp_path / "ex.json"
    ex.write_text(json.dumps(example_chart))
    mock_llm.return_value = _fake_llm(example_chart)
    out_root = tmp_path / "out"
    cg.ChartGenerator("KEY", str(profiles), str(out_root), str(ex)).run()
    assert (out_root / "Patient_1_").exists()
