import json, sys, random, pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from hyperscribe.libraries.constants import Constants
from evaluations.case_builders.synthetic_transcript_generator import TranscriptGenerator, main
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.constants import Constants as SpecConstants
from hyperscribe.structures.settings import Settings

def _fake_profiles_file(tmp_path: Path) -> Path:
    fake_profiles = tmp_path / "profiles.json"
    fake_profiles.write_text(json.dumps({"Patient 1": "AAA", "Patient 2": "BBB"}))
    return fake_profiles

@patch.object(random, "uniform", return_value=1.25)
@patch.object(random, "randint", return_value=3)
@patch.object(random, "choice")
def test_make_spec_deterministic(mock_choice, _mock_randint, _mock_uniform, tmp_path):
    tested = TranscriptGenerator(VendorKey("openai", "MY_KEY"), str(_fake_profiles_file(tmp_path)), str(tmp_path))
    
    mock_choice.side_effect = (
        ["short"] 
        + ["Clinician"] 
        + ["Patient"] * 2  
        + [SpecConstants.MOOD_POOL[0], SpecConstants.MOOD_POOL[1]]
        + [SpecConstants.PRESSURE_POOL[0]]
        + [SpecConstants.CLINICIAN_PERSONAS[0]]
        + [SpecConstants.PATIENT_PERSONAS[0]]
    )

    result = tested._make_spec()
    assert result["bucket"] == "short"
    assert result["turn_total"] == 3
    assert result["speaker_sequence"] == ["Clinician", "Patient", "Patient"]
    assert result["ratio"] == 1.25
    assert all(m in SpecConstants.MOOD_POOL for m in result["mood"])

@patch("evaluations.case_builders.synthetic_transcript_generator.generate_json", return_value=[{"speaker": "Clinician", "text": "Mid-visit note."}])
def test_generate_transcript_ok(mock_generate_json, tmp_path):
    tested = TranscriptGenerator(VendorKey("openai", "MY_KEY"), str(_fake_profiles_file(tmp_path)), str(tmp_path))

    result_transcript, result_spec = tested.generate_transcript_for_profile("stub profile")
    expected = [{"speaker": "Clinician", "text": "Mid-visit note."}]

    mock_generate_json.assert_called_once()
    assert result_transcript == expected
    assert "mid-visit note." in tested.seen_openings
    assert {"turn_total", "ratio", "bucket"} <= set(result_spec.keys())

@patch("evaluations.case_builders.synthetic_transcript_generator.generate_json", side_effect=lambda **kwargs: (_ for _ in ()).throw(ValueError("schema failed")))
def test_generate_transcript_bad_json_raises(mock_generate_json, tmp_path):
    tested = TranscriptGenerator(VendorKey("openai", "MY_KEY"), str(_fake_profiles_file(tmp_path)), str(tmp_path))
    with pytest.raises(ValueError):
        tested.generate_transcript_for_profile("stub profile")
    mock_generate_json.assert_called_once()

@patch("evaluations.case_builders.synthetic_transcript_generator.generate_json", return_value=[{"speaker": "Clinician", "text": "content"}])
def test_run_creates_files(mock_generate_json, tmp_path):
    tested = TranscriptGenerator(VendorKey("openai", "MY_KEY"), str(_fake_profiles_file(tmp_path)), str(tmp_path))
    tested.run(start_index=2, limit=1)

    result_dir = tmp_path / "Patient_2"
    assert (result_dir / "transcript.json").exists()
    assert (result_dir / "spec.json").exists()
    mock_generate_json.assert_called_once()

def test_build_prompt_includes_seen_openings(tmp_path):
    tested = TranscriptGenerator(VendorKey("openai", "MY_KEY"), str(_fake_profiles_file(tmp_path)), str(tmp_path))
    tested.seen_openings.add("previous first line")

    spec = {
        "turn_total": 2,
        "speaker_sequence": ["Clinician", "Patient"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": "",
    }

    sys_lines, user_lines = tested._build_prompt("stub patient", spec)
    result = "\n".join(sys_lines)
    assert "Avoid starting with any of these previous first lines" in result

@patch("evaluations.case_builders.synthetic_transcript_generator.generate_json", return_value=[{"speaker": "Clinician", "text": "Hello there"}])
def test_seen_openings_branch(mock_generate_json, tmp_path):
    tested = TranscriptGenerator(VendorKey("openai", "MY_KEY"), str(_fake_profiles_file(tmp_path)), str(tmp_path))
    assert not tested.seen_openings

    result_transcript, _ = tested.generate_transcript_for_profile("profile")
    assert result_transcript == [{"speaker": "Clinician", "text": "Hello there"}]
    assert "hello there" in tested.seen_openings

@patch("evaluations.case_builders.synthetic_transcript_generator.generate_json")
def test_generate_transcript_adds_seen_opening(mock_generate_json, tmp_path):
    expected = [{"text": "Hi there"}]
    mock_generate_json.return_value = expected

    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps({"Patient 1": "Mock narrative"}))
    output_path = tmp_path / "outdir"

    tested = TranscriptGenerator(VendorKey("openai", "MY_KEY"), input_path=input_path, output_root=output_path)
    result_transcript, result_spec = tested.generate_transcript_for_profile("Mock narrative")

    assert result_transcript == expected
    assert {"turn_total", "ratio", "bucket", "mood"} <= set(result_spec)
    assert "hi there" in tested.seen_openings
    mock_generate_json.assert_called_once()

@patch("evaluations.case_builders.synthetic_transcript_generator.generate_json")
def test_generate_transcript_adds_seen_opening_logic_branch(mock_generate_json, tmp_path):
    expected = [{"text": " Hello world!  "}]
    mock_generate_json.return_value = expected

    input_path = tmp_path / "in.json"
    input_path.write_text(json.dumps({"Patient 1": "Mock narrative"}))
    output_path = tmp_path / "outdir"

    tested = TranscriptGenerator(VendorKey("openai", "MY_KEY"), input_path=input_path, output_root=output_path)
    result_transcript, _ = tested.generate_transcript_for_profile("Mock narrative")

    assert result_transcript == expected
    assert "hello world!" in tested.seen_openings
    mock_generate_json.assert_called_once()

@patch("evaluations.case_builders.synthetic_transcript_generator.TranscriptGenerator")
def test_main_parses_args_and_calls_run(mock_transcript_generator, tmp_path, monkeypatch):
    tested = main
    dummy_settings = MagicMock()
    dummy_settings.llm_text = VendorKey("openai", "TRANSCRIPT_KEY")
    monkeypatch.setattr(Settings, "from_dictionary", classmethod(lambda cls, env: dummy_settings))

    input_path = tmp_path / "in.json"
    output_path = tmp_path / "outdir"
    monkeypatch.setattr(sys, "argv", [
        "prog", "--input", str(input_path), "--output", str(output_path),
        "--start", "3", "--limit", "7"
    ])

    tested()

    mock_transcript_generator.assert_called_once_with(
        vendor_key=dummy_settings.llm_text,
        input_path=input_path,
        output_root=output_path,
    )
    mock_transcript_generator.return_value.run.assert_called_once_with(start_index=3, limit=7)
