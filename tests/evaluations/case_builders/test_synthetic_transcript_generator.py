import json, random, argparse, pytest
from argparse import Namespace
from pathlib import Path
from argparse import ArgumentParser, Namespace
from unittest.mock import patch, MagicMock, call
from evaluations.case_builders.synthetic_transcript_generator import SyntheticTranscriptGenerator, HelperSyntheticJson
from evaluations.helper_evaluation import HelperEvaluation
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.constants import Constants as SpecConstants

def create_fake_profiles_file(tmp_path: Path) -> Path:
    fake_profiles = tmp_path / "profiles.json"
    fake_profiles.write_text(json.dumps({"Patient 1": "AAA", "Patient 2": "BBB"}))
    return fake_profiles

@patch.object(random, "uniform", return_value=1.25)
@patch.object(random, "randint", return_value=3)
@patch.object(random, "choice")
def test_make_spec_deterministic(mock_choice, _randint, _uniform, tmp_path):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(vendor_key, profiles, tmp_path)

    mock_choice.side_effect = (
        ["short"] 
        + ["Clinician"] 
        + ["Patient"] * 2  
        + [SpecConstants.MOOD_POOL[0], SpecConstants.MOOD_POOL[1]]
        + [SpecConstants.PRESSURE_POOL[0]]
        + [SpecConstants.CLINICIAN_PERSONAS[0]]
        + [SpecConstants.PATIENT_PERSONAS[0]]
    )

    spec = tested._make_spec()
    assert spec["bucket"] == "short"
    assert spec["turn_total"] == 3
    assert spec["speaker_sequence"] == ["Clinician", "Patient", "Patient"]
    assert spec["ratio"] == 1.25
    assert all(m in SpecConstants.MOOD_POOL for m in spec["mood"])

def test__build_prompt(tmp_path):
    tested = SyntheticTranscriptGenerator(VendorKey("openai", "MY_KEY"), create_fake_profiles_file(tmp_path), tmp_path)
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
    
    dummy_schema = {"type": "array"}
    system_lines, user_lines = tested._build_prompt("profile text", spec, dummy_schema)
    combined_system = "\n".join(system_lines)

    assert "Avoid starting with any of these previous first lines: previous first line" in combined_system


@patch.object(HelperSyntheticJson, "generate_json", return_value=[{"speaker": "Clinician", "text": "Sample text"}])
def test_generate_transcript__success(mock_generate_json, tmp_path):
    input_file = create_fake_profiles_file(tmp_path)
    output_dir = tmp_path / "output"

    tested = SyntheticTranscriptGenerator(vendor_key=VendorKey("openai", "KEY"), 
        input_path=input_file, output_path=output_dir)

    result_transcript, result_spec = tested.generate_transcript_for_profile("Sample profile")
    expected_transcript = [{"speaker": "Clinician", "text": "Sample text"}]

    args = mock_generate_json.call_args.args
    kwargs = mock_generate_json.call_args.kwargs
    calls = [call(*args, **kwargs)]
    assert mock_generate_json.mock_calls == calls
    assert result_transcript == expected_transcript
    assert result_transcript[0]["text"].lower().strip() in tested.seen_openings
    assert {"bucket", "turn_total", "ratio"} <= set(result_spec.keys())


@patch.object(HelperSyntheticJson, "generate_json", side_effect=ValueError("Invalid JSON"))
def test_generate_transcript__bad_json_raises(mock_generate_json, tmp_path):
    tested = SyntheticTranscriptGenerator(vendor_key=VendorKey("openai", "KEY"), 
        input_path=create_fake_profiles_file(tmp_path), output_path=tmp_path)

    with pytest.raises(ValueError) as exc_info:
        tested.generate_transcript_for_profile("Sample profile")

    assert "Invalid JSON" in str(exc_info.value)
    args = mock_generate_json.call_args.args
    kwargs = mock_generate_json.call_args.kwargs
    calls = [call(*args, **kwargs)]
    assert mock_generate_json.mock_calls == calls

@patch.object(HelperSyntheticJson, "generate_json", return_value=[{"speaker": "Clinician", "text": "Content"}])
def test_run(mock_generate_json, tmp_path):
    input_file = create_fake_profiles_file(tmp_path)
    output_dir = tmp_path / "output"
    tested = SyntheticTranscriptGenerator(vendor_key=VendorKey("openai", "KEY"),
        input_path=input_file, output_path=output_dir)

    tested.run(start_index=2, limit=1)
    result_directory = output_dir / "Patient_2"

    assert (result_directory / "transcript.json").exists()
    assert (result_directory / "spec.json").exists()
    args = mock_generate_json.call_args.args
    kwargs = mock_generate_json.call_args.kwargs
    calls = [call(*args, **kwargs)]
    assert mock_generate_json.mock_calls == calls

@patch("evaluations.case_builders.synthetic_transcript_generator.SyntheticTranscriptGenerator")
@patch("evaluations.case_builders.synthetic_transcript_generator.HelperEvaluation.settings")
@patch("evaluations.case_builders.synthetic_transcript_generator.argparse.ArgumentParser.parse_args")
def test_main(mock_parse_args, mock_settings, mock_generator_class):
    fake_input = Path("input.json")
    fake_output = Path("/output")
    fake_args = argparse.Namespace(input=fake_input, output=fake_output, start=5, limit=10)
    mock_parse_args.return_value = fake_args

    fake_vendor_key = VendorKey("openai", "DUMMY")
    dummy_settings = MagicMock()
    dummy_settings.llm_text = fake_vendor_key
    mock_settings.return_value = dummy_settings

    mock_instance = MagicMock()
    mock_generator_class.return_value = mock_instance

    SyntheticTranscriptGenerator.main()

    assert mock_generator_class.call_args == call(vendor_key=fake_vendor_key,
        input_path=fake_input, output_path=fake_output)
    assert mock_instance.run.call_args == call(start_index=5, limit=10)
