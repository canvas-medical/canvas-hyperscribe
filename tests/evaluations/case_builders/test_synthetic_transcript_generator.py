import json, random, argparse, pytest, hashlib
from argparse import Namespace
from pathlib import Path
from unittest.mock import patch, MagicMock, call
from evaluations.case_builders.synthetic_transcript_generator import SyntheticTranscriptGenerator, HelperSyntheticJson
from hyperscribe.structures.vendor_key import VendorKey
from evaluations.constants import Constants as SpecConstants

def create_fake_profiles_file(tmp_path: Path) -> Path:
    fake_profiles = tmp_path / "profiles.json"
    fake_profiles.write_text(json.dumps({"Patient 1": "AAA", "Patient 2": "BBB"}))
    return fake_profiles

def test__load_profiles(tmp_path):
    data = {"Alice": "profile1", "Bob": "profile2"}
    profiles_file = tmp_path / "profiles.json"
    profiles_file.write_text(json.dumps(data))

    dummy = Namespace(input_path=profiles_file)
    result = SyntheticTranscriptGenerator._load_profiles(dummy)
    assert result == data

@patch("evaluations.case_builders.synthetic_transcript_generator.random.choice")
def test__random_bucket(mock_choice):
    expected_keys = list(SpecConstants.TURN_BUCKETS.keys())
    forced_returns = expected_keys
    mock_choice.side_effect = forced_returns

    results = [SyntheticTranscriptGenerator._random_bucket() for _ in range(3)]
    assert results == forced_returns
    assert all(result in expected_keys for result in results)

    #mock calls
    expected_calls = [call(expected_keys) for _ in range(3)]
    assert mock_choice.mock_calls == expected_calls


@patch.object(random, "uniform", return_value=1.25)
@patch.object(random, "randint", return_value=3)
@patch.object(random, "sample") 
@patch.object(random, "choice")
def test__make_spec(mock_choice, mock_sample, _randint, _uniform, tmp_path):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(vendor_key, profiles, tmp_path)

    mock_choice.side_effect = (
        ["short"]
        + ["Clinician"]
        + ["Patient"] * 2
        + [SpecConstants.PRESSURE_POOL[0]]
        + [SpecConstants.CLINICIAN_PERSONAS[0]]
        + [SpecConstants.PATIENT_PERSONAS[0]]
    )

    mock_sample.return_value = [SpecConstants.MOOD_POOL[0], SpecConstants.MOOD_POOL[1]]

    spec = tested._make_spec()
    assert spec["bucket"] == "short"
    assert spec["turn_total"] == 3
    assert spec["speaker_sequence"] == ["Clinician", "Patient", "Patient"]
    assert spec["ratio"] == 1.25
    assert spec["mood"] == mock_sample.return_value

    expected_sample_calls = [call(SpecConstants.MOOD_POOL, k=2)]
    assert mock_sample.mock_calls == expected_sample_calls

    
    expected_calls = [
        call(list(SpecConstants.TURN_BUCKETS.keys())),
        call(["Clinician", "Patient"]),
        call(["Clinician", "Patient"]),
        call(["Clinician", "Patient"]),
        call(SpecConstants.PRESSURE_POOL),
        call(SpecConstants.CLINICIAN_PERSONAS),
        call(SpecConstants.PATIENT_PERSONAS),
    ]
    assert mock_choice.mock_calls == expected_calls

def test_schema_transcript(tmp_path):
    vendor_key = VendorKey(vendor="openai", api_key="MY_KEY")
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(vendor_key, profiles, tmp_path)
    spec = {"turn_total": 37}
    result = tested.schema_transcript(spec)
    expected = {
            "$schema": "http://json-schema.org/draft-07/schema#",
            "type": "array",
            "minItems": 37,
            "maxItems": 37,
            "items": {
                "type": "object",
                "properties": {
                    "speaker": {"type": "string",
                                "description": "Who is talking for this turn, either 'Clinician' or 'Patient'."},
                    "text":    {"type": "string",
                                "description": "Words spoken during the turn."},
                },
                "required": ["speaker", "text"],
                "additionalProperties": False,
            },
        }
    assert result == expected


def test__build_prompt(tmp_path):
    tested = SyntheticTranscriptGenerator(VendorKey("openai", "MY_KEY"), create_fake_profiles_file(tmp_path), tmp_path)

    spec = {
        "turn_total": 2,
        "speaker_sequence": ["Clinician", "Patient"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": "",
    }
    schema = {"type": "array"}

    system_prompt_no_previous, _ = tested._build_prompt("profile text", spec, schema)
    assert "Avoid starting with any of these previous first lines:" not in "\n".join(system_prompt_no_previous)

    tested.seen_openings.add("previous first line")
    system_prompt_previous_lines, user_prompt_previous_lines = tested._build_prompt("profile text", spec, schema)
    
    combined_sys = "\n".join(system_prompt_previous_lines)
    assert "Avoid starting with any of these previous first lines: previous first line" in combined_sys
    expected_system_md5 = "8407fd613773ae1c4494989d79fd4588"
    expected_user_md5   = "6257d98e369d9359b5900eec00953b5a"
    result_system_md5 = hashlib.md5("\n".join(system_prompt_previous_lines).encode()).hexdigest()
    result_user_md5 = hashlib.md5("\n".join(user_prompt_previous_lines).encode()).hexdigest()

    assert result_system_md5 == expected_system_md5
    assert result_user_md5 == expected_user_md5


@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt",
    return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_spec",
    return_value={
        "bucket": "short",
        "turn_total": 1,
        "speaker_sequence": ["Clinician"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": ""})
@patch.object(HelperSyntheticJson, "generate_json", return_value=[{"speaker": "Clinician", "text": "Sample text"}])
def test_generate_transcript_for_profile__success(mock_generate_json, mock_make_spec, mock_build_prompt, mock_schema_transcript, tmp_path):
    profiles = create_fake_profiles_file(tmp_path)
    tested = SyntheticTranscriptGenerator(
        vendor_key=VendorKey("openai", "KEY"), input_path=profiles, output_path=tmp_path)

    profile_text = "Sample profile"
    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda spec: expected_schema
    transcript, spec = tested.generate_transcript_for_profile(profile_text)

    _, kwargs = mock_generate_json.call_args
    assert kwargs["vendor_key"] == tested.vendor_key
    assert kwargs["schema"] == expected_schema
    assert kwargs["system_prompt"] == ["System Prompt"]
    assert kwargs["user_prompt"] == ["User Prompt"]

    expected_transcript = [{"speaker": "Clinician", "text": "Sample text"}]
    assert transcript == expected_transcript
    assert "sample text" in tested.seen_openings


@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt",
    return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_spec",
    return_value={
        "bucket": "short",
        "turn_total": 1,
        "speaker_sequence": ["Clinician"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": "",})
@patch.object(HelperSyntheticJson, "generate_json", side_effect=ValueError("Invalid JSON"))
def test_generate_transcript_for_profile__bad_json_raises(mock_generate_json, mock_make_spec, mock_build_prompt, mock_schema_transcript, tmp_path):
    profiles = create_fake_profiles_file(tmp_path)
    vendor_key=VendorKey("openai", "KEY")
    tested = SyntheticTranscriptGenerator(vendor_key, input_path=profiles, output_path=tmp_path)
    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda spec: expected_schema
    profile_text = "Sample profile"
    with pytest.raises(ValueError) as exc_info:
        tested.generate_transcript_for_profile(profile_text)
    assert "Invalid JSON" in str(exc_info.value)

    _, kwargs = mock_generate_json.call_args
    assert kwargs["vendor_key"] == tested.vendor_key
    assert kwargs["schema"] == expected_schema
    assert kwargs["system_prompt"] == ["System Prompt"]
    assert kwargs["user_prompt"] == ["User Prompt"]

@patch.object(SyntheticTranscriptGenerator, "schema_transcript")
@patch.object(SyntheticTranscriptGenerator, "_build_prompt",
    return_value=(["System Prompt"], ["User Prompt"]))
@patch.object(SyntheticTranscriptGenerator, "_make_spec",
    return_value={
        "bucket": "short",
        "turn_total": 1,
        "speaker_sequence": ["Clinician"],
        "ratio": 1.0,
        "mood": [],
        "pressure": "",
        "clinician_style": "",
        "patient_style": ""})
@patch.object(HelperSyntheticJson, "generate_json", return_value=[{"speaker": "Clinician", "text": "Content"}])
def test_run(mock_generate_json, mock_make_spec, mock_build_prompt, mock_schema_transcript, tmp_path):
    input_file = create_fake_profiles_file(tmp_path)
    output_dir = tmp_path / "output"
    tested = SyntheticTranscriptGenerator(
        vendor_key=VendorKey("openai", "KEY"), input_path=input_file, output_path=output_dir)
    expected_schema = {"type": "array"}
    mock_schema_transcript.side_effect = lambda spec: expected_schema

    #patient 2
    tested.run(start_index=2, limit=1)
    result_directory = output_dir / "Patient_2"
    assert (result_directory / "transcript.json").exists()
    assert (result_directory / "spec.json").exists()

    _, kwargs = mock_generate_json.call_args
    assert kwargs["vendor_key"] == tested.vendor_key
    assert kwargs["schema"] == expected_schema
    assert kwargs["system_prompt"] == ["System Prompt"]
    assert kwargs["user_prompt"] == ["User Prompt"]

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
